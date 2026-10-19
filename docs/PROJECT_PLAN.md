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

## 2. Deadline and milestones (today is Mon 2026-10-19)

| Milestone | Date | Definition |
|---|---|---|
| **M1: workable** | **Sat 2026-10-31** | `make up` starts the stack. Strava activities and Shortcut calories/protein land in Postgres. Hevy sessions are parsed to sets. SQL streak with the freeze rule works. Dashboard shows: greeting, day chooser, streak card, recovery card with freeze indicator, logged exercises card, calorie budget card, protein card. Bottom nav with 4 pages (Activities, Nutrition, Me may be minimal). CI green. |
| **M2: portfolio-ready** | **Fri 2026-11-13** | Everything in M1 plus: weekly calorie card, full Activities / Nutrition / Me pages, pipeline health panel, DQ checks visible, Core leftovers (calendar, trends), chosen Next features, hosting decision, README with diagram and screenshots. |

**Unconfirmed assumption: about 20 hours/week of capacity.** M1 is 12 days away. If real capacity is under about 15 h/week, M1 slips to about Wed Nov 4 and Slice 7 shrinks. Rob: confirm your weekly hours at the start of Slice 1.

### Cut lines (cut in this order if time slips; never cut the "never cut" list)
1. Slice 7b "Next" features (PRs, weekly summary, muscle volume, small forms)
2. Slice 7a trends (monthly first, then weekly)
3. Calendar view (week/month)
4. Weekly calorie card polish and the dashed overflow arc
5. Activities page set-by-set detail (fall back to raw description text)

**Never cut:** tests, idempotency, data-quality checks, quarantine, CI, README with diagram.

Early-warning checkpoints: Slice 4 not done by **Mon Oct 27** means Slice 6 pages Activities/Nutrition/Me become stubs for M1. Slice 5 not done by **Wed Oct 29** means tell Rob immediately and drop the weekly chart and Activities detail from M1.

## 3. Scope by priority

**Core:** set-level lifting data; daily calorie totals; week streak widget; calendar view (week/month); streaks; weekly/monthly trends; pipeline health panel; data-quality checks.

**Next:** recovery-day logging (the freeze, built in Slices 5-6 because the streak needs it); weight trend vs goal (needs a data source, see Backlog); personal records (estimated 1RM); weekly summary vs previous week; weekly volume per muscle group; protein tracking (dashboard cards in Slice 6); small manual-entry forms.

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
| Slice 0 | Build the iOS Shortcut that outputs dietary energy and dietary protein per logged food item. Send one real output (redact if needed) to `docs/samples/`. |
| Slice 0 | Send 3-5 more Hevy-in-Strava descriptions, including a bodyweight set, a cardio/time set, and a superset if you have them. One sample is already in `docs/samples/hevy_description_01.txt`. |
| Slice 1 | Confirm weekly hours (see section 2). |
| Slice 3 | Find your Mac's LAN IP, allow incoming connections for Docker Desktop in the macOS firewall prompt, run the Shortcut against `http://<mac-lan-ip>:8000`. |
| Slice 8 | Approve the hosting choice. |

## 5. Slices

Each slice: goal, deliverables, acceptance criteria (all testable). Tests listed are part of the slice.

### Slice 0: Spikes and samples (Mon Oct 19 to Tue Oct 20) `[ ]`
**Goal:** replace the two biggest unknowns with real data before designing around them.
- Strava OAuth works once, locally. `GET /athlete/activities` and `GET /activities/{id}` return a Hevy-logged activity. Confirm the `description`, `sport_type`, `start_date_local`, `timezone`, and `elapsed_time` fields exist in the detail response (the list endpoint may omit `description`).
- Shortcut output captured: the exact fields, units, timestamps, and whether it can filter by date range and send a window.
- Save redacted JSON samples in `docs/samples/`. Update the payload contract in `ARCHITECTURE.md` section 6.2 and record the decision in DECISIONS.
**Acceptance:** samples committed; open questions in `ARCHITECTURE.md` section 14 for Slice 0 are answered or escalated to Rob.

### Slice 1: Skeleton, CI (Tue Oct 20 to Thu Oct 22) `[ ]`
**Deliverables:** Compose with `postgres`, `api` (FastAPI, `GET /api/v1/health`), `airflow` (LocalExecutor), `web` (Vite hello page); Alembic baseline creating schemas; Makefile (see `CLAUDE.md`); `.env.example`; README quickstart; GitHub Actions (ruff, pytest with Postgres service, DAG import test, web typecheck/build/vitest); `docs/DECISIONS.md`.
**Acceptance:** fresh clone then `cp .env.example .env && make up` gives healthy services; `make check` green locally and in CI; Airflow UI reachable on localhost; API reachable from the iPhone at `http://<mac-lan-ip>:8000/api/v1/health`.

### Slice 2: Strava to raw (Airflow) (Thu Oct 22 to Sat Oct 24) `[ ]`
**Deliverables:** `scripts/strava_auth.py` (one-time OAuth); token refresh with storage in `ops.oauth_tokens`; DAG `strava_sync` (hourly, `catchup=False`, `max_active_runs=1`, retries with backoff); incremental watermark with a 7-day lookback; `raw.strava_activities` upsert by `strava_id`; `ops.pipeline_runs` row per run; rate-limit handling (read current limits from Strava docs).
**Acceptance:** run twice, row count unchanged and no duplicates; kill the run midway then rerun, still correct; an edited Strava description is picked up inside the lookback window; tests use recorded fixtures (no live API in CI); DAG import test passes.

### Slice 3: Health ingest endpoint (Sat Oct 24 to Sun Oct 25) `[ ]`
**Deliverables:** `POST /api/v1/ingest/health` with `X-API-Key`; Pydantic validation; `raw.health_batches` + `raw.health_samples`; rejects go to `ops.quarantine`; response `{received, accepted, rejected, batch_id}`; `scripts/send_sample_shortcut_payload.sh`; DAG `health_transform` (applies unapplied batches in order; each batch replaces its date window).
**Acceptance:** same payload sent twice leaves `core.fact_dietary_sample` unchanged; an edited payload (food entry changed or removed within the window) updates the day correctly; invalid unit/value is quarantined not dropped; wrong or missing API key returns 401; the real Shortcut on Rob's iPhone posts to the Mac over HTTP and rows appear.

### Slice 4: Core model and Hevy parser (Sun Oct 25 to Tue Oct 27) `[ ]`
**Deliverables:** `core.dim_date`, `dim_activity_type`, `dim_exercise`, `fact_activity`, `fact_set`; seed CSVs (activity types, exercise-to-muscle map); pure parser `parse_hevy(description) -> ParsedWorkout` with kg normalization; quarantine of unparseable lines with raw text and reason; re-parse is idempotent (replace sets per activity in one transaction).
**Acceptance (golden):** `docs/samples/hevy_description_01.txt` parses to **9 exercises, 22 sets, total volume 3490.90 kg** (rounded to 2 dp; the two lbs exercises are converted at 0.45359237 kg/lb; original value and unit are kept); a Strava activity without the Hevy marker is `not_hevy`, not an error; every unknown line becomes a quarantine row and the activity is `partial`, never silently dropped; at least 10 parser unit tests including blank lines, trailing spaces, lbs, and a garbage line.

### Slice 5: Marts, streak with freeze, data quality, pipeline health (Tue Oct 27 to Thu Oct 29) `[ ]`
**Deliverables:** `app.target_history` (budget/goal in effect per date), `app.recovery_day`; `mart.v_day_status`, `mart.v_streak`, `mart.v_daily_nutrition`; DQ checks (list in `ARCHITECTURE.md` section 9) writing `ops.dq_results`; `GET /api/v1/pipeline/health`.
**Acceptance:** every scenario in `ARCHITECTURE.md` section 8.4 passes as a SQL integration test against real Postgres; healing yesterday restores the streak; DQ failures appear in the endpoint; killing the Strava token produces a visible failed run and stale-freshness warning.

### Slice 6a: API + web shell + dashboard v0 (Thu Oct 29 to Sat Oct 31) `[ ]`  **= M1**
**Deliverables:** `GET /api/v1/dashboard`, `GET/PUT /api/v1/me`, `POST/DELETE /api/v1/recovery`; React app with bottom navigation (4 pages, Activities/Nutrition/Me can be minimal), API-key gate; dashboard cards from greeting through protein per `UI_SPEC.md`; visual verification loop with screenshots.
**Acceptance:** `UI_SPEC.md` section 12 checklist items for those cards pass; Rob opens it on his iPhone via the Mac's LAN IP and sees real data.

### Slice 6b: Complete pages and remaining dashboard card (Nov 1 to Nov 5) `[ ]`
Weekly calorie budget card; Activities page v1 (day-grouped list; lifting sessions expand to exercises and sets; runs show distance, pace, duration; unparsed descriptions shown as raw text with a quarantine tag); Nutrition page v1; Me page (targets form, pipeline health panel, DQ status).

### Slice 7: Core leftovers, then Next features (Nov 5 to Nov 10) `[ ]`
- **7a Core leftovers:** calendar (week/month toggle on Activities, tap a day to filter), weekly/monthly trends (training on Activities, calories/protein on Nutrition), using window functions (`LAG`, rolling averages).
- **7b Next (pick in this order while time lasts):** personal records by estimated 1RM (Epley `w * (1 + reps/30)`, `RANK`/`MAX OVER`); weekly summary vs previous week; weekly volume per muscle group; small manual-entry forms.

### Slice 8: Hosting decision, deploy, README (Nov 10 to Nov 14) `[ ]`
Research free hosting options (current pricing and limits, from official pages); present options with trade-offs; Rob approves; deploy only after approval. Finish README (framing line, architecture and ERD diagrams, screenshots, how to run, DQ list, design decisions, limitations, interview notes).

## 6. Resume claims tracker (claim only when Status is "built")

| Claim | Evidence required | Status |
|---|---|---|
| Airflow-orchestrated pipeline into a PostgreSQL star schema | DAGs running locally; `core` dims/facts; ERD in README | not built |
| Parser turning free-text workouts into set-level records | Golden test (22 sets, 3490.90 kg) in CI; parse-coverage metric | not built |
| Idempotent incremental loads | Run-twice tests for Strava and health; watermark + lookback | not built |
| Data-quality checks and CI | `ops.dq_results` populated; CI badge | not built |
| SQL window-function streaks and trends | `mart.v_day_status`/`v_streak` tests; trend views | not built |

## 7. Risks

| Risk | Mitigation |
|---|---|
| Shortcut payload differs from the contract | Slice 0 spike; health normalizer written only after samples exist |
| Strava rate limits / token expiry | Backoff, per-run detail cap, token refresh test, freshness DQ check |
| Airflow memory and learning curve on a laptop | LocalExecutor only; no Celery/Redis; keep tasks thin (SQL + small Python) |
| Hevy text has formats not in the sample (bodyweight, time, supersets) | Strict parser plus quarantine; collect samples in Slice 0; extend the parser by test |
| Single freeze surprises Rob on trips | Documented limitation; pause feature is in Backlog |
| Scope creep | Cut lines in section 2; Backlog below |
| Capacity | Confirm hours in Slice 1; re-plan at M1 checkpoints |

## 8. Backlog (not in scope; do not build without Rob's approval)

- Streak pause for injury/vacation (multi-day freeze). Known limitation: with one freeze, a multi-day absence breaks the streak.
- Weight trend vs goal: needs a data source (Apple Health body mass via the Shortcut, or manual entry). Rob to decide.
- Training-load view; `GET /streak` for Scriptable; CSV export.
- dbt for transforms; Great Expectations.
- Light mode; per-role DB users; reconcile Strava deletions; Airflow REST trigger from the ingest endpoint.

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
