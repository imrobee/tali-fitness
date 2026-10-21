# Decisions

One entry per key choice: the decision, why (1-2 lines), and the alternative rejected.
Newest slice at the bottom.

## Slice 0: spikes

**D1. Health data: replace per (local_date, type), applied synchronously at ingest.**
Why: samples carry no ids (confirmed by the spike), so an edited food entry can only be handled by replacing; replacing only the pairs present in a batch protects a day when one type comes back empty. Applying it in the ingest transaction removes a DAG and the lag.
Rejected: hash de-duplication (cannot see edits); whole-window replace (wipes a type that failed to load); a 10-minute `health_transform` DAG.
Known limitation: deleting the *last* entry of a type on a day does not propagate.

**D2. Body mass comes from the Shortcut (Apple Health "Weight", kg); the day's weight is the last reading of that day.**
MyNetDiary keeps one weight per day (a new weigh-in replaces the earlier one; confirmed in Health 2026-10-20), so the last-reading rule is a guard for other apps. Values are exact pound conversions: store in full, round only for display.
Why: no new data source or manual form needed. Rejected: manual weight entry.

**D3. Strava `start_date_local` is naive local time despite its trailing `Z`.**
Why: the spike showed `start_date_local` = `start_date` + 8 h with a `Z` on both. Parsing it as UTC would move evening workouts to the next day. Rejected: trusting the `Z`.

**D4. The Shortcut builds its JSON body as text (Combine Text + Text action, sent as a file).**
Why: Shortcuts' JSON request body turns a list of dictionaries into one string. Rejected: the JSON body editor.

**D5. The Shortcut runs on a "MyNetDiary is closed" automation, not a timed one.**
Why: Apple Health data is unreadable while the iPhone is locked; a timed automation on a locked phone never posted (spike, 2026-10-20). Closing the app happens while unlocked. Missed pushes are covered because each batch includes yesterday. Rejected: Time of Day automation.

**D6. `dim_exercise` uses `UNIQUE NULLS NOT DISTINCT (exercise_name, equipment)`.**
Why: with a plain unique, NULL equipment never conflicts, so every re-parse would insert duplicates. Rejected: a `''` sentinel for missing equipment.

**D7. DQ checks run in their own hourly `data_quality` DAG; 5 checks for M1, all 15 for M2, each with a pass and a fail test.**
Why: health data no longer passes through Airflow, so checks need their own schedule. Rejected: a `dq_checks` task inside `strava_sync`.

**D8. `calorie_status = not_set` (calories logged, no budget) is a filled neutral-gray marker and bar.** (Rob's call.)
Open risk: same shape as `within`, so it relies on the gray/green luminance difference in grayscale (UI_SPEC section 8).

**D17. One `fact_set` table with a `set_kind` column (`weight_reps`, `reps`, `distance_duration`, `duration`), nullable measure columns, and one `CHECK` per kind.** (Rob chose option A, 2026-10-20.)
Why: Hevy's Strava text has four set formats (samples 01 and 02); one table keeps "every set of a workout" in one place, and the database enforces which columns each kind fills. Volume counts only `weight_reps`.
Rejected: keeping weight and reps only (every cycling and plank set would be quarantined forever); a separate table per kind (four tables to join for one workout).

**D18. Exercise notes are stored in `fact_set.exercise_note`, repeated on each set of that exercise entry.**
Why: notes are optional, short, and only ever shown with their sets; no extra table to explain. Rejected: a separate exercise-entry table (cleaner normalization, more joins for no current use).

## Slice 1: skeleton and CI

**D9. Airflow runs as `airflow standalone` in one container (LocalExecutor, metadata in a separate `airflow` Postgres database).**
Why: the lightest official way to run Airflow 3; measured about 1.0 GB RAM. Rejected: the official docker-compose (CeleryExecutor, Redis, a worker; 4 GB minimum, 8 GB recommended on macOS).

**D10. Airflow login comes from `.env` by pre-writing the simple auth manager's passwords file (`pipeline/start_airflow.sh`).**
Why: Airflow 3 has no config option for a fixed password; the docs say the passwords file can be edited. Rejected: `simple_auth_manager_all_admins` (no login at all); reading a random generated password from logs.

**D11. Every command runs in Docker; CI runs `make check`, exactly like local.**
Why: one environment to explain; the host needs only Docker and make (Rob's Node 23 is not supported by Vitest). Rejected: host virtualenv/Node; separate GitHub service containers (a second copy of the setup).

**D12. Versions pinned exactly, choosing releases at least two weeks old.**
Why: FastAPI shipped several breaking releases the week of 2026-10-20; brand-new releases are the riskiest. Rejected: `latest` / caret ranges.

**D13. Python 3.13 for the API, matching the `apache/airflow:3.3.2` image.**
Why: one Python version across the repo (CLAUDE.md conventions). Rejected: 3.12.

**D14. Web lint with oxlint and TypeScript 6.0, as the current Vite `react-ts` template ships them.**
Why: fewer custom changes to the template; TypeScript 7 is a brand-new major. Rejected: adding ESLint (CLAUDE.md originally said eslint); TypeScript 7.

**D15. Postgres is published on the Mac at `127.0.0.1:5433`.**
Why: Rob's own Postgres already holds 5432. Containers still use 5432 internally. Rejected: stopping the local Postgres.

**D16. Migration tests use a fixed throwaway database name (`migrations_test`).**
Why: `CREATE DATABASE` cannot take a bound parameter, and a constant avoids building SQL from strings. Rejected: a random per-test name.

### Dependencies (reason for each)

| Package | Version | Why |
|---|---|---|
| fastapi | 0.142.2 | The API framework named in ARCHITECTURE.md |
| uvicorn[standard] | 0.54.0 | ASGI server that runs FastAPI; `--reload` in dev |
| SQLAlchemy | 2.1.3 | One way to talk to Postgres (`text()` + parameters) from API and Airflow |
| psycopg[binary] | 3.3.6 | Postgres driver used by SQLAlchemy |
| alembic | 1.20.0 | Forward-only migrations written as explicit SQL |
| pytest | 9.1.1 | Test runner for API and pipeline |
| httpx | 0.28.1 | Required by FastAPI's `TestClient` |
| apache/airflow image | 3.3.2 | Orchestrator; current release, at least two weeks old |
| ruff (Docker image) | 0.16.10 | Python lint and format, no local install |
| react, react-dom | 19.3.0 | UI library from the Vite template |
| vite | 8.3.2 | Dev server and build tool |
| @vitejs/plugin-react | 6.1.2 | React support for Vite (template) |
| typescript | 6.0.3 | Strict typing (template) |
| oxlint | 1.87.0 | Web lint (template) |
| vitest | 5.0.3 | Unit tests for pure web functions |
| @types/node, @types/react, @types/react-dom | 24.19.1, 19.3.0, 19.3.0 | Type definitions (template) |

## Slice 2: Strava to raw

**D19. Run bookkeeping: `start_run` opens the `ops.pipeline_runs` row, each task records its own failure, `close_run` (ALL_DONE) fails anything still `running`.**
Why: Airflow 3 tasks cannot read other tasks' states, so a final `record_run` task could not tell what failed. Rejected: one `record_run` task inspecting upstream states.

**D20. `fetch_activities` and `load_raw` are one task, writing each activity and the watermark in one transaction.**
Why: 90 days of JSON must not pass through XCom, and per-activity commits make a killed run keep its progress (tested). Rejected: separate fetch and load tasks handing payloads over XCom.

**D21. Detail fetches go to activities not yet loaded first, then already-loaded ones, capped at 50 per run.**
Why: with oldest-first only, a backfill with more than 50 activities inside the 7-day lookback would re-fetch the same ones every run and never finish (a test proves the reordering matters). Rejected: plain oldest-first.

**D22. The Strava client uses the Python standard library (`urllib`), like the Slice 0 spike.**
Why: four HTTP calls do not justify a new dependency, and the code is the same as the spike Rob already ran. Rejected: `requests`/`httpx`.

**D23. One-time authorization is `make strava-auth`, running `include/strava/auth.py` in the Airflow container.**
Why: it reuses the client and `save_tokens`, and the container already has the Strava keys and database access. Rejected: a separate host script (`scripts/strava_auth.py`) needing its own Python setup.

**D24. Strava location data is dropped before landing: `map`, `start_latlng`, `end_latlng`, `segment_efforts`.** (Rob, 2026-10-20.)
Why: GPS routes show where runs start (often home); Strava has no option to leave them out, and `activity:read_all` even returns data inside privacy zones. Nothing downstream uses them, so replaying the parser from `raw` is unaffected. Migration 0003 scrubbed the 24 rows loaded earlier; a full search of the stored JSON found no coordinates afterward.
Rejected: keeping raw fully unchanged and masking only before hosting (the data would sit in local backups until then); switching to `activity:read` plus Strava privacy zones (loses "Only You" activities and still sends most of the route). The one exception to "raw is stored exactly as received".

## Slice 3: Health ingest

**D25. `raw.health_samples` keeps accepted samples exactly as received (kJ stays kJ); conversion happens in `core.apply_health_batch`.**
Why: keeps `raw` raw, so a conversion bug can be fixed and replayed; the full request body is also kept in `raw.health_batches.payload`. Rejected: storing converted values in `raw`.

**D26. Validation splits in two: a broken envelope or window rejects the whole request (422); a bad sample is quarantined and the rest is accepted.**
Why: one odd food entry should not block a day's data, and nothing is dropped silently. Added reason codes `invalid_sample` (missing field or non-number value) and `unknown_type` to the spec's list. Rejected: rejecting the whole batch on any bad sample.

**D27. An identical re-send returns 200 `duplicate: true`, stores no data, but writes an `ops.pipeline_runs` row; a new batch returns 201.**
Why: with the "MyNetDiary closed" trigger most pushes are re-sends; logging them lets the freshness check tell "Shortcut alive, nothing new" from "Shortcut broken". Rejected: logging nothing for duplicates.

**D28. `core.dim_date` is built in Slice 3 (2020-2035, 5,844 rows), not Slice 4.**
Why: `core.fact_dietary_sample` references it. Rejected: a `date_key` without a foreign key until Slice 4.

**D29. The ingest endpoint reads the raw body itself (async) and runs the database work in a worker thread.**
Why: the exact bytes are needed for the sha256 duplicate check and for storing the payload as received; blocking database calls must not stall FastAPI's event loop. Rejected: a Pydantic body parameter (FastAPI would parse the body first, losing the original bytes).

**D30. The duplicate check fingerprints a canonical form of the batch (samples sorted, keys ordered), not the raw bytes.**
Why: the Shortcut returns the same samples in a different order on each run, so two identical pushes (13:36 and 13:37 on 2026-10-21) were both stored as new batches. The data stayed correct (each batch replaces its pairs), but `raw` grew by a batch per push. The raw bytes are still stored unchanged in `payload`. Rejected: hashing raw bytes.

**D31. The Shortcut's date filters use `FilterAfter` (start of the day before yesterday), not `WindowFrom`.**
Why: Shortcuts compares dates in "Start Date is after" by calendar day, so "after yesterday 12:00 AM" silently dropped all of yesterday (found live 2026-10-21; it worked on day one only because the window then started a day earlier). `window.from` still sends yesterday. While debugging, 33 older samples were correctly quarantined as `outside_window`; they were marked resolved with a note, not deleted. Rejected: "is in the last N days" (rolling hours, not calendar days, so its edges are unclear).
