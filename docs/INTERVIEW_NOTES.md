# Interview notes

Talking points from building this project, one slice at a time. Each point: **what** I did, **why**, and the **trade-off**. Only built and tested work is listed here (see the resume claims tracker in `PROJECT_PLAN.md`).

## The 30-second pitch

> "My training, running and nutrition data lives in separate apps that don't talk to each other, so I built a pipeline that joins them."

Strava activities are **pulled** hourly by Airflow; Apple Health nutrition is **pushed** by an iOS Shortcut to a FastAPI endpoint. Both land unchanged in a `raw` layer in Postgres, then SQL and a Python parser build a Kimball star schema in `core`. Everything runs in Docker Compose, and CI runs the same `make check` as my laptop.

## Numbers worth remembering

| Fact | Value |
|---|---|
| Hevy golden test | 9 exercises, 22 sets, **3,490.90 kg** (exact 3490.8973504), reproduced from live Strava data |
| Second golden test | 6 exercise entries, 12 sets of 3 non-weight kinds, 2 notes |
| Strava backfill | 24 activities over 90 days; ~5 seconds per normal run |
| Strava API use | ~145 of 1,000 daily read calls (14%) |
| Airflow memory | ~1.0 GB (official Compose setup: 4 GB minimum) |
| Tests | 42 API + 126 pipeline + 2 web, all in CI |

## Architecture and design

**ELT, not ETL.** Sources land unchanged in `raw`; transforms run afterwards inside Postgres.
- Why: the Hevy text format kept evolving (four set kinds were discovered in real samples). With raw kept, a parser fix replays history without re-calling Strava.
- Trade-off: raw keeps data I don't need, so I made one deliberate exception (location, below). Health ingest also validates at the door, so it is "ELT with validation for pushed data".

**Layered schemas:** `raw` (as received, never edited) → `core` (star schema) → `mart` (business rules) with `ops` (pipeline bookkeeping) and `app` (user input) alongside. Same idea as dbt staging/marts or medallion bronze/silver/gold.

**Pull vs push.** Strava is polled because it is a remote API; Apple Health can only leave the phone when the phone sends it, so the Shortcut pushes.

**Polling hourly instead of syncing on app open.**
- Why: the app stays fast and works when Strava is down; Airflow stays the only code calling Strava (one place for tokens, retries, run logs); one-run-at-a-time prevents duplicate syncs.
- Trade-off: up to an hour's delay in seeing a workout. It never affects *which day* it counts for, because the day comes from the activity's own start time.
- Next steps I designed (Backlog): "sync if stale" on app open that asks Airflow to run; webhooks once hosted.

**Privacy: GPS is dropped before landing.** Strava has no option to omit route and coordinates, and the `activity:read_all` scope even includes privacy-zone data. I strip `map`, `start_latlng`, `end_latlng`, `segment_efforts` at load and scrubbed existing rows with a migration. This is the textbook case where a little ETL beats pure ELT: mask sensitive data before it lands.

## Slice 1: skeleton and CI

- **Airflow `standalone` in one container** instead of the official 5-service Compose setup. ~1 GB vs 4 GB+. Trade-off: less like production, which doesn't matter for local development.
- **CI runs `make check` inside the same containers as local**, so "works on my machine" means "works in CI". Trade-off: slower CI because it builds images.
- **Forward-only migrations**, each tested on a fresh database and re-run to prove the second run changes nothing.
- **Exact version pins, at least two weeks old.** FastAPI shipped several breaking releases the week I started. Trade-off: missing the newest fixes.
- **A test must be able to fail.** My DAG import test passed with a broken file in the folder, because Airflow skips files that don't mention "airflow" and "dag". I re-proved it with a realistic broken DAG.

## Slice 2: Strava into raw (Airflow)

- **Watermark plus a 7-day lookback.** Incremental loads that still catch descriptions edited after upload. Trade-off: re-fetching the last week every hour.
- **One transaction per activity**, writing the row and advancing the watermark together. A crash loses at most one activity; the rerun continues. Tested by killing a run midway.
- **New activities first under a rate cap.** A backfill with more than 50 activities in the lookback window would otherwise re-fetch the same ones forever. A deliberately broken version proved the test catches it.
- **Run bookkeeping designed around Airflow 3.** Tasks can't read each other's states, so each task writes its own failure into `ops.pipeline_runs`, and a final always-run task closes anything unfinished.
- **Tests use a fake Strava built from a real recorded response.** Fast, deterministic, no live API calls in CI.

## Slice 3: Health ingest endpoint

- **Replace per (day, type), in one transaction.** Edits and deletions in Apple Health propagate, re-sends change nothing, and a type that fails to load can't wipe a day. A test that fails if whole days are replaced proves it.
- **Validate at the door, quarantine instead of drop.** A broken envelope rejects the request; a bad sample is quarantined with a reason while the rest is accepted. A live debugging session produced 33 quarantined rows instead of silent data loss.
- **`raw` keeps what the phone actually sent** (kJ stays kJ). Conversion happens in `core`, so it can be replayed.
- **One source of "today"** on the server, with a test clock (`NOW_OVERRIDE`) honored only in dev and test, so date-dependent tests are deterministic.

## Slice 4: core star schema and Hevy parser

- **Pure parser plus golden tests.** Text in, sets out, no I/O, with exact expected totals from real samples. Weights use `Decimal`, so 3490.8973504 is exact.
- **Replay from raw.** A `PARSER_VERSION` constant plus "which raw version was parsed" means improving the grammar re-processes history automatically.
- **Constraints live in the database**: `UNIQUE NULLS NOT DISTINCT` for exercises without equipment, and one CHECK per set kind (weight, reps, distance, time). Each was proven by breaking it on purpose.
- **Never guess, never drop.** Unknown lines go to quarantine with their line number; re-parsing replaces them instead of duplicating them.
- **One rule in one place.** Only the parser decides "is this Hevy text?"; SQL only copies data, so the two can't disagree.

## Slice 5: business rules and data quality

- **The streak and freeze rule live in SQL, as functions taking `p_today`.** `LAG` answers "did the previous day qualify?" (the single freeze), and a running `SUM` of missed days splits days into chains (gaps-and-islands). Tests control the clock instead of depending on the real date.
- **17 scenarios written as notation** (`Q R R Q Q T`) run as tests against real Postgres, including healing yesterday with a workout or with the freeze. Removing the "previous day qualified" condition fails them.
- **Targets are history, not a setting.** A budget change inserts a row effective from that day, so a past day is always judged by the budget it had.
- **Data-quality checks are plain SQL with their thresholds inside**, run hourly by their own DAG, each with a pass test and a fail test. A failing check is a stored finding, not a crashed pipeline. Trade-off: no framework like Great Expectations, in exchange for checks anyone can read.
- **Freshness counts "the Shortcut reached us", not "new data arrived"**, so a quiet day with duplicate pushes isn't mistaken for a broken pipeline.

## Bugs found, and how (good "tell me about a time" stories)

| Bug | How it surfaced | Fix |
|---|---|---|
| A task argument named `run_id` made every Airflow run fail before any code ran | First live run hung in retries; read the task log | Renamed it, and added a test that checks every task argument against Airflow's own list of reserved names |
| Re-parse decision compared timestamps from two different clocks | Tests with fixed times failed | Compare the exact raw version parsed instead (clock-independent) |
| Identical Health re-sends were stored as new batches | Live data: two identical pushes a minute apart | The Shortcut reorders samples; fingerprint a sorted, canonical form instead of raw bytes |
| Yesterday's food disappeared from Health pushes | Live data the morning after day one | iOS Shortcuts compares dates by calendar day, not time; filter from the day before yesterday |
| Strava's local start time ends in a misleading `Z` | Comparing UTC and local fields in the spike | Treat it as naive local time; a test keeps an 11:30 pm workout on its own day |

**The habit behind most of these:** after writing a key test, I break the code on purpose and confirm the test fails. A passing test proves nothing until you've seen it fail.
