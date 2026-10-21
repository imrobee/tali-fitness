# Project Plan

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done. Update this file at the end of every slice.

## 1. Goal and how it maps to the job posting

Portfolio project for entry-level Data Engineer roles. The target posting emphasizes:

| Posting emphasis | Where this project shows it |
|---|---|
| Python ETL | Airflow DAGs, Strava client, Hevy text parser |
| Strong SQL / RDBMS | PostgreSQL schemas, constraints, window-function streaks and trends |
| Data modeling and warehousing | Star schema in `core` (dims + facts), marts as views |
| Structured and unstructured data | Strava JSON (structured) and Hevy free-text descriptions (unstructured) |
| Data quality | DQ checks with severities, quarantine table, parse-coverage metric |
| BI dashboards | The web dashboard and pages |
| Orchestration | Airflow DAGs with retries, idempotent tasks, run logging |
| Stakeholder communication | README, DECISIONS log, weekly summary view |

## 2. Milestones (no deadlines; built in order, as far as time allows)

| Milestone | Definition |
|---|---|
| **M1: workable** | `make up` starts the stack. Strava activities and Shortcut calories/protein land in Postgres. Hevy sessions are parsed to sets. SQL streak with the freeze rule works. Dashboard shows: greeting, day chooser, streak card, recovery card with freeze indicator, logged exercises card, calorie budget card, protein card. Bottom nav with 4 pages (Activities and Nutrition may be minimal; Me has at least the targets form). 5 DQ checks run in the `data_quality` DAG. CI green. |
| **M2: portfolio-ready** | Everything in M1 plus: weekly calorie card, full Activities / Nutrition / Me pages, `/pipeline/health` and the pipeline health panel, all 15 DQ checks (pass and fail test each) visible, full screenshot set, Core leftovers (calendar, trends), chosen Next features, hosting decision, README with diagram and screenshots. |

### Priority order (lowest priority first; trim from the top if scope must shrink; never cut the "never cut" list)
1. Slice 7b "Next" features (weight trend, PRs, weekly summary, muscle volume, small forms)
2. Slice 7a trends (monthly first, then weekly)
3. Calendar view (week/month)
4. Weekly calorie card polish and the dashed overflow arc
5. Activities page set-by-set detail (fall back to raw description text)

**Never cut:** tests, idempotency, data-quality checks, quarantine, CI, README with diagram.

## 3. Scope by priority

**Core:** set-level lifting data; daily calorie totals; week streak widget; calendar view (week/month); streaks; weekly/monthly trends; pipeline health panel; data-quality checks.

**Next:** recovery-day logging (the freeze, built in Slices 5-6 because the streak needs it); weight trend vs goal (Apple Health Body Mass via the Shortcut; built first in Slice 7b, after 7a); personal records (estimated 1RM); weekly summary vs previous week; weekly volume per muscle group; protein tracking (dashboard cards in Slice 6); small manual-entry forms.

**Dropped:** never-miss-twice flag. The freeze rule enforces it (see `ARCHITECTURE.md` section 8).

**Stretch:** training-load view; `GET /streak` JSON for an iOS Scriptable widget or Shortcut notification; CSV export.

**Out of scope:** multi-user onboarding, AI/LLM features, social features, native iOS app, PWA/service worker/push, streak pause for injury/vacation (see Backlog).

### Where features live
| Feature | Page |
|---|---|
| Greeting, day chooser, streak, recovery, exercises card, calorie/protein/weekly cards | Dashboard |
| Day-grouped activity list, set-level detail, calendar (week/month), training trends, PRs, volume by muscle | Activities |
| Calorie budget, protein, weekly calorie cards, calorie/protein trends | Nutrition |
| Nickname, calorie budget, protein goal, timezone, API key, pipeline health panel, DQ status | Me |

## 4. Rob's tasks (the agent cannot do these)

| When | Task |
|---|---|
| Before Slice 0 | Install Docker Desktop. Create a private GitHub repo (CI needs it). |
| Slice 0 | Create a Strava API application (callback domain `localhost`), note client ID and secret, put them in `.env` (never commit). |
| Slice 0 | Build the iOS Shortcut that outputs dietary energy and dietary protein per logged food item, and Body Mass (kg; MyNetDiary keeps one per day). Send one real output (redact if needed) to `docs/samples/`. |
| Slice 0 | Done: `docs/samples/hevy_description_02.txt` covers bodyweight, distance/time, and timed sets plus exercise notes. Hevy has no supersets or warm-up/drop/failure sets in its Strava text. |
| Slice 3 | Set a real `API_KEY` in `.env`; in the Shortcut, change the URL to `http://<mac-lan-ip>:8000/api/v1/ingest/health` and add the header `X-API-Key`; close MyNetDiary and check rows appear. |
| Slice 8 | Approve the hosting choice. |

## 5. Slices

Each slice: goal, deliverables, acceptance criteria (all testable). Tests listed are part of the slice.

### Slice 0: Spikes and samples (in parallel with Slice 1) `[x]`
Slices 0 and 1 share one branch, `slice-1-foundation` (exception to one branch per slice). Spike scripts: `scripts/spikes/`.
**Goal:** replace the two biggest unknowns with real data before designing around them.
- Strava OAuth works once, locally. `GET /athlete/activities` and `GET /activities/{id}` return a Hevy-logged activity. Confirm the `description`, `sport_type`, `start_date_local`, `timezone`, and `elapsed_time` fields exist in the detail response (the list endpoint may omit `description`).
- Shortcut output captured: the exact fields, units, timestamps, and whether it can filter by date range and send a window.
- Include Body Mass in the Shortcut (kg) alongside dietary energy and protein. Done: MyNetDiary keeps one weight per day.
- Save redacted JSON samples in `docs/samples/`. Update the payload contract in `ARCHITECTURE.md` section 6.2 and record the decision in DECISIONS.
**Acceptance:** samples committed; open questions in `ARCHITECTURE.md` section 14 for Slice 0 are answered or escalated to Rob.

### Slice 1: Skeleton, CI `[x]`
**Airflow:** get it running with the lightest official setup; no tuning or extras.
**Deliverables:** Compose with `postgres`, `api` (FastAPI, `GET /api/v1/health`), `airflow` (LocalExecutor), `web` (Vite hello page); Alembic baseline creating schemas; Makefile (see `CLAUDE.md`); `.env.example`; README quickstart; GitHub Actions (ruff, pytest with Postgres service, DAG import test, web typecheck/build/vitest); `docs/DECISIONS.md`.
**Acceptance:** fresh clone then `cp .env.example .env && make up` gives healthy services; `make check` green locally and in CI; Airflow UI reachable on localhost; API reachable from the iPhone at `http://<mac-lan-ip>:8000/api/v1/health`.

### Slice 2: Strava to raw (Airflow) `[x]`
**Deliverables:** `make strava-auth` (one-time OAuth); token refresh with storage in `ops.oauth_tokens`; DAG `strava_sync` (hourly, `catchup=False`, `max_active_runs=1`, retries with backoff); incremental watermark with a 7-day lookback; `raw.strava_activities` upsert by `strava_id`; `ops.pipeline_runs` row per run; rate-limit handling (read current limits from Strava docs).
**Acceptance:** run twice, row count unchanged and no duplicates; kill the run midway then rerun, still correct; an edited Strava description is picked up inside the lookback window; a unit test shows `start_date_local` with a trailing `Z` is stored as naive local time and gets the right `local_date`; tests use recorded fixtures (no live API in CI); DAG import test passes.

### Slice 3: Health ingest endpoint `[x]`
**Deliverables:** `POST /api/v1/ingest/health` with `X-API-Key`; Pydantic validation; `raw.health_batches` + `raw.health_samples`; rejects go to `ops.quarantine`; response `{batch_id, received, accepted, rejected, duplicate}`; `core.apply_health_batch(batch_id)` called in the ingest transaction (replaces only the `(local_date, type)` pairs present in the batch); `ops.pipeline_runs` row per ingest; `scripts/send_sample_shortcut_payload.sh`. No health DAG (`ARCHITECTURE.md` 6.2).
**Acceptance:** same payload sent twice leaves `core.fact_dietary_sample` unchanged; an edited payload (food entry changed, or one of several entries removed) updates that day and type correctly; a batch missing a type for a day leaves that day's existing rows of that type untouched; a failure mid-batch rolls back raw and core; invalid unit/value is quarantined not dropped; wrong or missing API key returns 401; the real Shortcut on Rob's iPhone posts to the Mac over HTTP and rows appear.

### Slice 4: Core model and Hevy parser `[x]`
**Deliverables:** `core.dim_date`, `dim_activity_type`, `dim_exercise`, `fact_activity`, `fact_set`; seed CSVs (activity types, exercise-to-muscle map); pure parser `parse_hevy(description) -> ParsedWorkout` handling the four set kinds and exercise notes (`ARCHITECTURE.md` section 7) with kg, metre, and second normalization; `fact_set.set_kind` with one `CHECK` per kind; quarantine of unparseable lines with raw text and reason; re-parse is idempotent (replace sets per activity in one transaction); `dim_exercise` uses `UNIQUE NULLS NOT DISTINCT (exercise_name, equipment)`.
**Acceptance (golden):** `docs/samples/hevy_description_01.txt` parses to **9 exercises, 22 sets, total volume 3490.90 kg** (rounded to 2 dp; the two lbs exercises are converted at 0.45359237 kg/lb; original value and unit are kept); `docs/samples/hevy_description_02.txt` parses to **6 exercise entries, 12 sets, 2 notes, 55 reps, 52 km, 8,642 s, volume 0** with `parse_status = ok`; a row violating its kind's `CHECK` is rejected by the database; a Strava activity without the Hevy marker is `not_hevy`, not an error; every unknown line becomes a quarantine row and the activity is `partial`, never silently dropped; at least 10 parser unit tests including blank lines, trailing spaces, lbs, and a garbage line; parsing the golden sample twice leaves the `dim_exercise` row count unchanged (covers exercises with NULL equipment).

### Slice 5: Marts, streak with freeze, data quality, pipeline health `[x]`
**Deliverables:** `app.target_history` (budget/goal in effect per date), `app.recovery_day`; `mart.fn_day_status(p_today)`, `mart.fn_streak(p_today)`, `mart.fn_daily_nutrition(p_from, p_to)`; DAG `data_quality` (hourly) running the 5 M1 checks (`strava_freshness`, `health_freshness`, `activity_unique`, `row_reconcile`, `hevy_parse_coverage`) and writing `ops.dq_results`.
**Acceptance:** every scenario in `ARCHITECTURE.md` section 8.4 passes as a SQL integration test against real Postgres; healing yesterday restores the streak; each of the 5 checks has a pass test and a fail test; killing the Strava token produces a failed run in `ops.pipeline_runs` and a `strava_freshness` warning in `ops.dq_results`.

### Slice 6a: API + web shell + dashboard v0 `[~]`  **= M1**
**Deliverables:** `GET /api/v1/dashboard`, `GET/PUT /api/v1/me`, `POST/DELETE /api/v1/recovery`; React app with bottom navigation (4 pages, Activities/Nutrition can be minimal), API-key gate; minimal Me page with the targets form (calorie budget, protein goal, saved effective today); dashboard cards from greeting through protein per `UI_SPEC.md`; visual verification loop with screenshots for 3 scenarios (`midweek`, `at_risk`, `edge_empty`) at iPhone size (393x852) only.
**Acceptance:** `UI_SPEC.md` section 12 checklist items for those cards pass; Rob opens it on his iPhone via the Mac's LAN IP and sees real data.

### Slice 6b: Complete pages and remaining dashboard card `[ ]`
Weekly calorie budget card; Activities page v1 (day-grouped list; lifting sessions expand to exercises and sets; runs show distance, pace, duration; unparsed descriptions shown as raw text with a quarantine tag); Nutrition page v1; Me page (pipeline health panel, DQ status); `GET /api/v1/pipeline/health` (moved from Slice 5); the remaining 10 DQ checks, each with a pass and a fail test; the full screenshot set (all scenarios, both viewports).

### Slice 7: Core leftovers, then Next features `[ ]`
- **7a Core leftovers:** calendar (week/month toggle on Activities, tap a day to filter), weekly/monthly trends (training on Activities, calories/protein on Nutrition), using window functions (`LAG`, rolling averages).
- **7b Next (pick in this order while time lasts):** weight trend vs goal (body mass from the Shortcut; daily weight = last reading of the day, `ARCHITECTURE.md` section 14 #8); personal records by estimated 1RM (Epley `w * (1 + reps/30)`, `RANK`/`MAX OVER`); weekly summary vs previous week; weekly volume per muscle group; small manual-entry forms.

### Slice 8: Hosting decision, deploy, README `[ ]`
Research free hosting options (current pricing and limits, from official pages); include **Strava webhooks** (push on create/update/delete instead of hourly polling; needs a public HTTPS callback URL, so only possible once hosted); present options with trade-offs; Rob approves; deploy only after approval. **Privacy before hosting:** `raw.strava_activities` payloads contain GPS (`map`, `start_latlng`, `end_latlng`), which reveals where runs start; done early in Slice 2 (DECISIONS D24): stripped at load and from existing rows by migration 0003. Re-check before deploying that no other location data has appeared. Finish README (framing line, architecture and ERD diagrams, screenshots, how to run, DQ list, design decisions, limitations, interview notes).

## 6. Resume claims tracker (claim only when Status is "built")

| Claim | Evidence required | Status |
|---|---|---|
| Airflow-orchestrated pipeline into a PostgreSQL star schema | DAGs running locally; `core` dims/facts; ERD in README | partial: `strava_sync` runs hourly raw -> core star schema (`dim_date`, `dim_activity_type`, `dim_exercise`, `fact_activity`, `fact_set`, `fact_dietary_sample`); ERD in README pending (Slice 8) |
| Parser turning free-text workouts into set-level records | Golden tests (22 sets, 3490.90 kg; 12 mixed-kind sets) in CI; parse-coverage metric | partial: parser and both golden tests built (Slice 4); parse-coverage DQ check in Slice 5 |
| Idempotent incremental loads | Run-twice tests for Strava and health; watermark + lookback | built: run-twice tests in CI for Strava (Slice 2, watermark + 7-day lookback) and health (Slice 3, replace per day and type, canonical duplicate check) |
| Data-quality checks and CI | `ops.dq_results` populated; CI badge | partial: CI built (Slice 1); 5 of 15 DQ checks built with pass and fail tests, writing `ops.dq_results` hourly (Slice 5); the other 10 in Slice 6b |
| SQL window-function streaks and trends | `mart.fn_day_status`/`fn_streak` tests; trend views | partial: streak with the freeze rule built (`LAG` + gaps-and-islands running `SUM`), all 17 scenarios in CI (Slice 5); trends in Slice 7a |

## 7. Risks

| Risk | Mitigation |
|---|---|
| Shortcut payload differs from the contract | Slice 0 spike; health normalizer written only after samples exist |
| Strava rate limits / token expiry | Backoff, per-run detail cap, token refresh test, freshness DQ check |
| Airflow memory and learning curve on a laptop | LocalExecutor only; no Celery/Redis; keep tasks thin (SQL + small Python) |
| Hevy text has formats not in the sample (bodyweight, time, supersets) | Strict parser plus quarantine; collect samples in Slice 0; extend the parser by test |
| Single freeze surprises Rob on trips | Documented limitation; pause feature is in Backlog |
| Scope creep | Priority order in section 2; Backlog below |

## 8. Backlog (not in scope; do not build without Rob's approval)

- Streak pause for injury/vacation (multi-day freeze). Known limitation: with one freeze, a multi-day absence breaks the streak.
- Training-load view; `GET /streak` for Scriptable; CSV export.
- dbt for transforms; Great Expectations.
- Light mode; per-role DB users; reconcile Strava deletions.
- Cheaper Strava polling (decided to wait, 2026-10-20: about 145 of 1,000 daily read calls today). (a) Skip night hours: cron `0 6-23 * * *` with the DAG time zone set to Asia/Manila (Airflow defaults to UTC). (b) Hourly runs fetch only new activities; one morning run re-checks the 7-day lookback for edited descriptions. (b) matters more: today every run re-fetches the whole week, so cost grows with activity count and could reach the daily limit in a very busy week.
- Shareable **Health Push** Shortcut: an iCloud link (or a signed `.shortcut` file via macOS `shortcuts sign`) in the README instead of rebuilding by hand. Use the Shortcut's import questions so each person enters their own server URL and API key at install; the shared copy must never contain Rob's key. Includes the day-granular date filter fix (ARCHITECTURE.md 6.2).
- "Sync now" / refresh-if-stale on app open: when the dashboard loads and the last successful Strava sync is older than N minutes, the API triggers `strava_sync` through Airflow's REST API (`max_active_runs=1` prevents doubles) and the UI shows "Syncing..." then refetches. Airflow stays the only code that calls Strava. Also a manual **Sync now** button (`POST /api/v1/sync/strava`, API key, 2-minute cooldown). For Apple Health the server cannot reach the phone, so a **Sync Health** button opens `shortcuts://run-shortcut?name=Health%20Push` to run the Shortcut from Safari (verify on the iPhone first).

## 9. README skeleton (Slice 8)

1. Problem statement (the framing line)
2. Architecture diagram (Mermaid from `ARCHITECTURE.md`) and ERD
3. What it does (screenshots of the four pages)
4. Tech stack and why (links to DECISIONS)
5. Data quality (list of checks, quarantine, parse coverage)
6. How to run locally (`make up`)
7. Testing and CI
8. Limitations and future work
9. Interview talking points
