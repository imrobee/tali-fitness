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
| Tests | 144 API + 195 pipeline + 145 web, all in CI |

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

## Slice 6a: API and dashboard

- **Rules in SQL, wording in Python, pixels in React.** The recovery card's state is one SQL function that both the card and `POST /recovery` use, so the button never offers something the server refuses. The API only adds text and shapes one payload per screen.
- **Logic out of components.** Ring maths, number and date formatting, screen-reader labels and form validation are pure TypeScript functions with unit tests; components only lay them out. Trade-off: more files, but every number on screen is tested without a browser.
- **The URL is the state.** The selected day lives in `?date=`, so the back button, refresh and the bottom tabs all keep it, with no global store.
- **Deterministic screenshots from a separate demo stack.** Its own database (`app_demo`, and the seed script refuses any other name), its own key, and a frozen clock, so the same scenario draws the same picture every time and demo data can't touch real data.
- **Accessibility built in.** Shape, not colour, carries meaning (circle, dot, square), every chart has a text label, and contrast was checked token by token. Trade-off: I changed two spec colours to pass, and recorded why.

## Slice 6b: all 15 data-quality checks, pipeline health, the full pages

- **15 data-quality checks, each a plain SQL file with its thresholds inside, each with a pass and a fail test.** Checks guarding a constraint (no orphans, no nulls) prove the fail case by dropping the constraint inside a rolled-back transaction. On real data, one check found an exercise with no muscle group on its first run.
- **Warnings mean "look at your data", failures mean "the pipeline is wrong".** Outliers warn; broken guarantees fail. A failing check is a stored finding, not a crashed DAG.
- **One definition of "stale".** The health panel's ok / delayed / failed uses the same thresholds as the freshness checks, and the server sends its own clock, so the page can't say "4 days ago" next to "Delayed".
- **Fetch on demand.** The Activities list is one query with totals computed in SQL; a session's sets load only when you open it. The golden number (22 sets, 3,490.90 kg) reads the same through the API.
- **Accessibility as a test, not a hope.** At 200% zoom, two cards clipped; fixed so circles keep their 32px minimum and wrap instead.

## Slice 7a: calendar and trends with window functions

- **Trends are SQL window functions, not app code.** `LAG` compares each week or month with the one before; `AVG ... ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` gives the 7-day rolling average. Both are mart functions taking `p_today`, so tests fix the clock.
- **The first bar still gets a comparison.** Each trend computes one hidden period before the ones shown, so `LAG` has a value for the oldest bar. Removing that trick made 7 of the 19 SQL tests fail, which is how I know they guard it.
- **Missing data is not zero.** Averages count logged days only (`AVG` skips NULLs), and the 7-day average ends yesterday because today is still being logged. Trade-off: a week with one logged day can show a misleading average, so the card always says how many days it covers.
- **Compare finished periods only.** Three days of this week against all of last week always reads as a drop; the running period is drawn "so far" and the headline compares the last finished one.
- **The server owns the calendar.** It returns full Monday-Sunday weeks and where the arrows can go; tapping a day filters the list to it, from any month.

## Slice 7b: weight trend against a goal

- **One weigh-in a day, by the same replace as calories.** A batch replaces the days it has a weight for and leaves other days alone, so a re-sent batch changes nothing. Tests replay a batch and check the day's last reading wins, whatever order the samples arrive in.
- **The goal has its own history table.** Saving the calorie budget writes a new target row; a goal column there would have gone blank on that row. Keeping goals in their own effective-dated table means each setting is changed on its own.
- **The change is a window function on a calendar, not on weigh-ins.** `LAG 7` compares this day's 7-day average with the one 7 days earlier. The query reads 13 days back so both sides exist; a gap is shown as a gap, never filled in.
- **A migration can be wrong about old data.** Migration 0009 created the table but did not copy the weigh-ins already in `raw`, so the live app showed no weight. Migration 0010 fills it in; the lesson is to check the live data after every migration, not just the tests.
- **Bugs found by the tests:** the test helper converted a 7 am Manila reading to the previous UTC day, and the change was empty for a single day because the window was one week too short. Both were fixed, and a broken rule was put back on purpose to check each test fails.

## Slice 7b (continued): units, records, muscle volume, weekly summary

- **Units are presentation, storage is canonical.** Every weight is kept in kg; kg or lb is a profile setting applied when shown, with the exact 0.45359237. Switching never rewrites data, so it is lossless both ways. A test caught a rounding bug: converting the on-screen "72.6 kg" made a 160 lb goal 160.1 lb, so the page now converts the stored value.
- **Personal records with two window functions.** `RANK()` picks each exercise's best estimated 1RM (Epley, 1-12 reps), and a running `MAX() OVER (... ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)` finds the best before it, so the page can say how much the record improved.
- **LAG needs like-for-like rows.** Muscle volume cross-joins every muscle group with every week, so a group not trained this week is a 0 compared with last week, not a missing row that LAG would skip.
- **One summary from the existing functions.** The weekly summary reuses the trend functions (already LAG-based) for the last finished week and adds qualifying days and weight with their own LAG.

## Slice 7c: Sync now

- **Event-triggered runs of a scheduled DAG.** The button asks the API, the API asks Airflow's REST API to run `strava_sync` now, and Airflow stays the only code that talks to Strava. Trade-off: the run still takes Airflow's queue time (6 seconds live), but there is one code path for loading data.
- **Verify the API you call.** The Airflow reference page renders with JavaScript, so I read the endpoints from the running Airflow 3.3.2's own OpenAPI spec: a JWT from `/auth/token`, then `POST /api/v2/dags/{id}/dagRuns` with `logical_date: null`.
- **Guard rails in layers.** A 2-minute cooldown in the database, a refusal while a run is in progress (ignoring "running" rows older than 30 minutes, which are crash leftovers), and the DAG's `max_active_runs=1` as the last line.
- **Test at the HTTP boundary.** The tests start a real local HTTP server playing Airflow, so the client's actual requests (path, body, bearer token, URL-encoded run id) are checked, and an Airflow error is shown to never leak the password.

## Bugs found, and how (good "tell me about a time" stories)

| Bug | How it surfaced | Fix |
|---|---|---|
| A task argument named `run_id` made every Airflow run fail before any code ran | First live run hung in retries; read the task log | Renamed it, and added a test that checks every task argument against Airflow's own list of reserved names |
| Re-parse decision compared timestamps from two different clocks | Tests with fixed times failed | Compare the exact raw version parsed instead (clock-independent) |
| Identical Health re-sends were stored as new batches | Live data: two identical pushes a minute apart | The Shortcut reorders samples; fingerprint a sorted, canonical form instead of raw bytes |
| Yesterday's food disappeared from Health pushes | Live data the morning after day one | iOS Shortcuts compares dates by calendar day, not time; filter from the day before yesterday |
| Strava's local start time ends in a misleading `Z` | Comparing UTC and local fields in the spike | Treat it as naive local time; a test keeps an 11:30 pm workout on its own day |
| The rebuilt web app returned 500s: "Failed to resolve import react-router" | First run against real data after adding packages | Docker kept the old `node_modules` in an anonymous volume; `make up` now renews anonymous volumes (the database volume is named and untouched) |
| "Last sync 4 days ago" next to a "Delayed" status | Looking at the demo screenshot, whose server clock is frozen | The page measured time from the phone's clock and the status from the server's; the API now sends its own `now` |
| Two cards clipped at 200% zoom | Rendering the dashboard at 197px wide (a phone at 200%) | The ring now scales to the card and the streak week wraps instead of overflowing |
| The recovery card changed height between states | Comparing the three screenshots side by side | The minimum height fitted only one-line states; it is now computed from the type sizes, and measured equal (132.6px) in every state |
| The Activities page crashed when a picked day's activities arrived before the dashboard | Rendering the new Activities page in the screenshot run (a blank page, a `RangeError` in the console) | The list now waits for the server's today; a page test fakes the slow dashboard and fails without the fix |
| The Week / Month switch pushed past the card edge at 200% zoom | Measuring horizontal scroll at 197px wide | Card headers wrap; trend charts keep only the first and last axis labels at that width |
| Switching the goal to pounds showed 160.1 lb for a 160 lb goal | A page test of the kg / lb switch | The page converted the rounded on-screen value; it now uses the stored goal while the field is untouched, and never re-saves it |
| The dashboard was 21px too wide at 200% zoom, but no element stuck out | Measuring scroll width, then hiding cards one by one | A `width: 1%` table-column trick became a 1px box when the rows stacked, and its text spilled past the card; bounding boxes do not include spilled text |

**The habit behind most of these:** after writing a key test, I break the code on purpose and confirm the test fails. A passing test proves nothing until you've seen it fail.
