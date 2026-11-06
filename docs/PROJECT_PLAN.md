# Project Plan

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done. Update this file at the end of every slice.

## Status at a glance (2026-10-21)

| Slice | Status | What was cut or changed (reasons in `DECISIONS.md`) |
|---|---|---|
| 0 Spikes and samples | `[x]` done | Shared a branch with Slice 1. Body mass added to the Shortcut; MyNetDiary keeps one weight per day (D2). Shortcut sends JSON built as text (D4), runs when MyNetDiary closes (D5), filters dates from the day before yesterday (D31). Hevy has four set kinds plus notes, no supersets or warm-up sets (D17). Spike scripts kept in `scripts/spikes/`. |
| 1 Skeleton, CI | `[x]` done | Airflow `standalone` in one container (D9). CI runs `make -k check` in the same containers instead of GitHub service containers (D11, D48). Postgres on Mac port 5433 (D15). oxlint instead of ESLint; TypeScript 6.0; Python 3.13 (D13, D14). |
| 2 Strava to raw | `[x]` done | `fetch_activities` + `load_raw` merged into `sync_activities`; `start_run`/`close_run` replace `record_run` (D19, D20). New activities fetched first under the cap (D21). `make strava-auth` replaces `scripts/strava_auth.py` (D23). GPS dropped before landing, pulled forward from Slice 8 (D24). |
| 3 Health ingest | `[x]` done | Applied synchronously; no `health_transform` DAG (D1). `core.dim_date` built here, not Slice 4 (D28). Duplicates logged as runs; canonical fingerprint (D27, D30). Extra reason codes, 201/200/413 responses (D26). |
| 4 Core + Hevy parser | `[x]` done | Option A `set_kind` (D17). Re-parse by raw version and `PARSER_VERSION` (D33). Seeds reloaded each run (D34). New `Cardio` group (D36). |
| 5 Marts, streak, DQ | `[x]` done | `GET /pipeline/health` moved to 6b. 5 of 15 DQ checks (rest in 6b). `fn_daily_nutrition` is a function, not a view (D37). `ops.dq_results` has no severity column (D39). `data_quality` at minute 30 (D40). |
| 6a API + web + dashboard (**M1**) | `[x]` done (PR #6; iPhone check passed 2026-10-21) | API: `GET /dashboard`, `GET/PUT /me`, `POST/DELETE /recovery`, migration 0007, 32 tests (D41-D44). Web: bottom nav, key gate, dashboard greeting through protein, Me targets form, minimal Activities/Nutrition reusing cards (D65), 47 new web tests. Separate demo stack and 3 iPhone screenshots (D66). Icons inline instead of `react-icons` (D59); flame colour changed (D62). |
| 6b Pages + rest (**M2 UI**) | `[x]` done (PR #7) | All 15 DQ checks (D69, D70); `/pipeline/health` and the Me panel (D71); `/activities` and the Activities page with set detail (D73, D74); weekly calorie card on Dashboard and Nutrition (D75); Nutrition reuses `/dashboard`, no `/nutrition` endpoint (D72); 14 screenshots, 3 scenarios at iPhone and desktop plus Activities, Nutrition and Me (D76); 200% zoom fixed (D77). Nothing from the cut line was cut. |
| 7 Leftovers + Next | `[~]` 7a-7c merged (PRs #8, #9); 7d built and green, waiting on Rob's iPhone check | 7a: trends and calendar (D79-D84). 7b: weight, kg/lb, records, muscle volume, Last week (D85-D93). 7c: Sync now (D94, D95). 7d: new streak rules with relaxed weekends, vacation breaks and the calorie ring (D96-D101). Open: "small manual-entry forms" (7b) undefined. |
| 8a Sign-in and ingest token | `[~]` built and green, waiting on Rob's checklist (`docs/AUTH_SPEC.md` section 13) | Local only, nothing deployed. Steps 1-9 done: D105-D115. Left for acceptance: Rob signs in with Google at `http://localhost:5173` (sets `ALLOWED_GOOGLE_SUB`), a second account is denied, the Shortcut posts with the new token, the old `API_KEY` is retired. |
| 8b Demo mode | `[~]` all four steps built and green (plus Rob's isolation and editing round, and the demo polish round: real-time clock and a 36-day story, the tour rebuilt with Rob's copy, How it works rewritten, D124-D127); waiting on Rob's commit and a look at http://localhost:5174 | Built on `ui-polish` at Rob's request, not its own branch. Steps: 1 isolation, 2 seed through the real pipeline, 3 tour, 4 How it works (D118). |
| 8 Hosting + README | `[ ]` not started | Includes evaluating Strava webhooks. GPS privacy already done (D24). |

Plan-level changes: all deadlines and time gates removed (D45); Rob runs every git command (D46); interview notes live in `docs/INTERVIEW_NOTES.md` (D57). See `docs/HANDOFF.md` for the exact next step.

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
2. Slice 7c Sync now
3. Slice 7a trends (monthly first, then weekly)
4. Calendar view (week/month)
5. Weekly calorie card polish
6. Activities page set-by-set detail (fall back to raw description text)

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
| Before Slice 0 | Done: Docker Desktop installed; private GitHub repo `imrobee/fitness-tracker`. |
| Slice 0 | Done: Strava API application created; keys in `.env`. |
| Slice 0 | Done: iOS Shortcut "Health Push" sends dietary energy, protein, and body mass; samples in `docs/samples/`. |
| Slice 0 | Done: `docs/samples/hevy_description_02.txt` covers bodyweight, distance/time, and timed sets plus exercise notes. Hevy has no supersets or warm-up/drop/failure sets in its Strava text. |
| Slice 2 | Done: `make strava-auth` run once; `strava_sync` switched on in Airflow. |
| Slice 3 | Done: real `API_KEY` set; Shortcut posts to `http://<mac-lan-ip>:8000/api/v1/ingest/health` with `X-API-Key`; duplicate re-send confirmed live. |
| Slice 5 | **Open:** switch on the `data_quality` DAG in the Airflow UI (it starts paused). |
| Slice 1 | **Open:** confirm CI logs show real test counts (run `gh auth login`, or paste the "passed" lines from the Actions log). |
| Slice 6a | Done: app opened on the iPhone over the Mac's LAN IP with real data (2026-10-21). |
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

### Slice 6a: API + web shell + dashboard v0 `[x]`  **= M1**
**Deliverables:** `GET /api/v1/dashboard`, `GET/PUT /api/v1/me`, `POST/DELETE /api/v1/recovery`; React app with bottom navigation (4 pages, Activities/Nutrition can be minimal), API-key gate; minimal Me page with the targets form (calorie budget, protein goal, saved effective today); dashboard cards from greeting through protein per `UI_SPEC.md`; visual verification loop with screenshots for 3 scenarios (`midweek`, `at_risk`, `edge_empty`) at iPhone size (393x852) only.
**Acceptance:** `UI_SPEC.md` section 12 checklist items for those cards pass; Rob opens it on his iPhone via the Mac's LAN IP and sees real data.

### Slice 6b: Complete pages and remaining dashboard card `[x]`
**Checkpoints (one commit each):** (1) the 10 remaining DQ checks; (2) `/pipeline/health` and the Me panel; (3) Activities API and page; (4) weekly card and Nutrition; (5) screenshots and docs.
**Acceptance:** all 15 DQ checks run in `data_quality`, each with a pass and a fail test; `/pipeline/health` matches ARCHITECTURE 10 with threshold tests; `/activities` is day-grouped, newest first, last 30 days by default, and the real Hevy session reads 9 exercises, 22 sets, 3,490.90 kg through it; every `UI_SPEC.md` section 12 item passes; screenshots for the 3 scenarios at 393x852 and 1280x800 plus the Activities, Nutrition and Me pages; Rob opens the new pages on his iPhone.
**Cut line (first to go):** the weekly card's step line for mid-week budget changes; then set-by-set detail on Activities (fall back to the raw description).
**Deliverables:** Weekly calorie budget card; Activities page v1 (day-grouped list; lifting sessions expand to exercises and sets; runs show distance, pace, duration; unparsed descriptions shown as raw text with a quarantine tag); Nutrition page v1; Me page (pipeline health panel, DQ status); `GET /api/v1/pipeline/health` (moved from Slice 5); the remaining 10 DQ checks, each with a pass and a fail test; the full screenshot set (all scenarios, both viewports).

### Slice 7: Core leftovers, then Next features `[ ]`
- **7a Core leftovers:** calendar (week/month toggle on Activities, tap a day to filter), weekly/monthly trends (training on Activities, calories/protein on Nutrition), using window functions (`LAG`, rolling averages).
  **Checkpoints (one commit each):** (1) migration 0008: `mart.fn_periods`, `fn_training_trend`, `fn_nutrition_trend`, `fn_nutrition_rolling`, with SQL tests; (2) `GET /calendar`, `GET /trends/training`, `GET /trends/nutrition`, with API tests; (3) calendar card and the day filter on Activities; (4) trend cards on Activities and Nutrition; (5) demo history, screenshots, docs.
  **Acceptance:** every trend number comes from SQL (`LAG` for the change against the previous period, `AVG ... ROWS 6 PRECEDING` for the 7-day average); SQL tests cover an empty period, a not-logged day left out of averages (not counted as 0), a budget change inside a period, the current period marked partial, and the first shown period still getting its `LAG` from the period before; the calendar shows full Monday-Sunday weeks, cannot move past today or before the first data month; tapping a day lists only that day's activities, from any month; screenshots of both pages with trends; 200% zoom has no horizontal scroll.
  **Cut line (first to go):** monthly grain (weekly only); then the calendar's week view (month only); then the nutrition trend's protein line.
- **7b Next (pick in this order while time lasts):** weight trend vs goal (body mass from the Shortcut; daily weight = last reading of the day, `ARCHITECTURE.md` section 14 #8); personal records by estimated 1RM (Epley `w * (1 + reps/30)`, `RANK`/`MAX OVER`); weekly summary vs previous week; weekly volume per muscle group; small manual-entry forms.
- **7b also (Rob, 2026-10-22):** a kg / lb weight unit on Me that every weight on every page follows (D89).
- **7c Sync now (D78):** a **Sync now** button on the Me page's Data and sync panel calls `POST /api/v1/sync/strava` (API key, 2-minute cooldown, `409` while a run is active). The API triggers `strava_sync` through Airflow's REST API (`max_active_runs=1` prevents doubles); Airflow stays the only code that calls Strava. The UI shows "Syncing..." and refetches when the run finishes. Optional: refresh-if-stale on app open (last successful sync older than N minutes). A **Sync Health** button opens `shortcuts://run-shortcut?name=Health%20Push` (verify on the iPhone first).
  **Acceptance:** API tests for the trigger, the cooldown, and an Airflow error (Airflow's API mocked at the HTTP boundary); one live run triggered from the button lands a new activity; the Airflow credentials live only in `.env`.
  **Cut line:** refresh-if-stale on app open first, then the Sync Health button.

- **7d Streak rules (Rob, 2026-10-27):** four kinds of day (success, over budget, rest, missed); a missed day, two over days or two rest days in a row end the streak; relaxed weekends (setting on Me, from today) and vacation or injury periods where only a missed day ends it; a "How your streak works" card on Me; the calorie marker becomes a ring (grey, green, orange with a "!" gap). The recovery card stays as a manual rest day.
  **Acceptance:** ARCHITECTURE 8 rewritten and its 20 mandatory scenarios plus weekend, vacation and recovery-card tests pass in CI; each rule proven by breaking it; `/me` saves relaxed weekends from today; `/vacation` sets, changes and ends a break, refuses overlaps, keeps past ones; the ring in screenshots; 200% zoom with no horizontal scroll.
  **Cut line (first to go):** the at-risk and pending messages that name the reason; then the "Last break" line.

### Slice 8a: Google sign-in and a scoped ingest token `[~]`
Spec: `docs/AUTH_SPEC.md` (Rob, 2026-10-28). Replaces the shared API key: Google sign-in (OIDC) for exactly one account with server-side sessions, an Origin check on every state-changing request, a hashed bearer token for the Shortcut valid on `POST /ingest/health` only, startup guards, hardening, and leak-prevention tests in CI. **Local only:** production guards are built and tested, nothing is deployed.
**Steps (one checkpoint each, `make check` green after each):** (1) config, secrets and startup guards; (2) ingest token; (3) sessions table and cookie; (4) Origin check and route protection; (5) Google OIDC endpoints; (6) front end; (7) hardening; (8) leak-prevention tests and CI; (9) docs.
**Acceptance:** every case in AUTH_SPEC sections 11 and 12 passes in CI; the guards refuse a bad production config; a real Google sign-in works at `http://localhost:5173` on the Mac; a second Google account is denied; the Shortcut posts with the new token; the old key works nowhere. Signing in with Google on the iPhone moves to Slice 8 (Google refuses IP-address redirect URIs, so it needs an HTTPS URL); phone testing in dev uses key mode on the LAN URL.
**Cut line (first to go):** the pre-commit config; then the separate database role (logged as a Slice 8 task); then `Permissions-Policy` and `Cross-Origin-Opener-Policy`.

### Slice 8b: Demo mode `[~]` (built; Rob's check pending)
**Goal:** a recruiter presses Demo, with no sign-in, and lands in the full app on synthetic data, with a guided tour that shows how the pipeline works.
**Acceptance:**
- The demo is its own service on its own database (`app_demo`), and holds no credential that opens the real one; tests prove a demo visit cannot read real data, and a real session is unaffected.
- Read-only on the server: every write is 403 `demo_read_only`, and the database role can only SELECT.
- Rate and size limits on the public routes.
- The data comes from synthetic raw payloads run through the real parser, core load and DQ checks; it is deterministic, dated relative to today, and reseeded idempotently.
- A spotlight tour (data file, 6-8 steps, its stated facts checked against the code; at 375x812 its sheet never covers its target, with Technical details off or on), a "Demo data" badge, and a "How it works" page in plain prose.
- The demo always tells a believable story on real time: a 10-day streak, a budget, parsed lifting sessions, records, no failed runs; the tour's numbers come from the last rebuild and are tested.
**Cut line (first to go):** the tour's auto-start; then the hand-drawn data-flow diagram; then rebuilding `at_risk`/`edge_empty` on the pipeline seed.
**Done:** step 1 (isolation, D118); step 2 (pipeline-built, deterministic, relative-dated demo data with a reseed at startup, D119); step 3 (the spotlight tour from a data file, lineage checked against the code, D120); the round after it: the demo service holds `demo_reader` only, a daily GitHub Actions reseed in one transaction with a self-heal, and a visitor's own Me settings applied at read time and never saved (D121, D122); step 4 (How it works, D123, and the production checklist in ARCHITECTURE 13b); the demo polish round (2026-11-05): the empty-demo root cause fixed and a rolling 36-day story with no failures (D124), the tour's sheet and spotlight rebuilt (D125), Rob's tour copy with one Technical details switch and claims tests (D126), How it works rewritten as prose from a data file (D127); the streak explainer (a ? on the streak card and the Me page's list from one file, its examples and claims checked against the streak SQL, D129); the streak string, a tour step on the name, and the wordmark on every page (D130).

### Slice 8: Hosting decision, deploy, README `[ ]`
**Auth carried over from 8a:** sign in with Google on the iPhone at the HTTPS URL; a test that the host's deploy config never declares `APP_ENV=dev` (D106); the API's database role without DDL rights (D115); `FORWARDED_ALLOW_IPS` set to the proxy's address; the production redirect URI in Google Cloud Console. **Hosted public demo:** a dedicated `APP_ENV=demo`: read-only (every non-GET route returns 403), no auth routes, no real credentials, the HTTPS-only guards on; it must never run as dev. Research free hosting options (current pricing and limits, from official pages); include **Strava webhooks** (push on create/update/delete instead of hourly polling; needs a public HTTPS callback URL, so only possible once hosted); present options with trade-offs; Rob approves; deploy only after approval. **Privacy before hosting:** `raw.strava_activities` payloads contain GPS (`map`, `start_latlng`, `end_latlng`), which reveals where runs start; done early in Slice 2 (DECISIONS D24): stripped at load and from existing rows by migration 0003. Re-check before deploying that no other location data has appeared. Finish README (framing line, architecture and ERD diagrams, screenshots, how to run, DQ list, design decisions, limitations, interview notes).

## 6. Resume claims tracker (claim only when Status is "built")

| Claim | Evidence required | Status |
|---|---|---|
| Airflow-orchestrated pipeline into a PostgreSQL star schema | DAGs running locally; `core` dims/facts; ERD in README | partial: `strava_sync` runs hourly raw -> core star schema (`dim_date`, `dim_activity_type`, `dim_exercise`, `fact_activity`, `fact_set`, `fact_dietary_sample`); ERD in README pending (Slice 8) |
| Parser turning free-text workouts into set-level records | Golden tests (22 sets, 3490.90 kg; 12 mixed-kind sets) in CI; parse-coverage metric | partial: parser and both golden tests built (Slice 4); parse-coverage DQ check in Slice 5 |
| Idempotent incremental loads | Run-twice tests for Strava and health; watermark + lookback | built: run-twice tests in CI for Strava (Slice 2, watermark + 7-day lookback) and health (Slice 3, replace per day and type, canonical duplicate check) |
| Data-quality checks and CI | `ops.dq_results` populated; CI badge | partial: CI built (Slice 1); all 15 DQ checks built with pass and fail tests, run hourly by `data_quality` into `ops.dq_results` (Slices 5 and 6b); `ops.dq_results` fills once Rob switches the DAG on |
| SQL window-function streaks and trends | `mart.fn_day_status`/`fn_streak` tests; trend functions | built: streak rules with `LAG` of the day's kind and leniency + gaps-and-islands running `SUM`, 20 mandatory scenarios plus weekend and vacation cases in CI (Slice 5, rewritten in 7d); weekly/monthly trends with `LAG` and a 7-day rolling `AVG ... ROWS 6 PRECEDING`, 19 SQL tests in CI (Slice 7a) |

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
- Per-role DB users; reconcile Strava deletions. (Light mode was built on `ui-polish` with the Tali colours, 2026-11-04; D116.)
- Cheaper Strava polling (decided to wait, 2026-10-20: about 145 of 1,000 daily read calls today). (a) Skip night hours: cron `0 6-23 * * *` with the DAG time zone set to Asia/Manila (Airflow defaults to UTC). (b) Hourly runs fetch only new activities; one morning run re-checks the 7-day lookback for edited descriptions. (b) matters more: today every run re-fetches the whole week, so cost grows with activity count and could reach the daily limit in a very busy week.
- Shareable **Health Push** Shortcut: an iCloud link (or a signed `.shortcut` file via macOS `shortcuts sign`) in the README instead of rebuilding by hand. Use the Shortcut's import questions so each person enters their own server URL and API key at install; the shared copy must never contain Rob's key. Includes the day-granular date filter fix (ARCHITECTURE.md 6.2).

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
