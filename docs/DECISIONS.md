# Decisions

One entry per key choice: the decision, why (1-2 lines), and the alternative rejected.
Grouped by slice; plan, process, and cross-cutting decisions are at the bottom (D45 onward).
Numbers are in the order decisions were made, so D17-D18 sit under Slice 0.

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
Why: one odd food entry should not block a day's data, and nothing is dropped silently. Added reason codes `invalid_sample` (missing field or non-number value) and `unknown_type` to the spec's list, plus 413 `payload_too_large` for bodies over 1 MB. Rejected: rejecting the whole batch on any bad sample.

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

## Slice 4: Core model and Hevy parser

**D32. The Python parser alone decides whether an activity is Hevy; the SQL transform only copies raw into `fact_activity`.**
Why: one place for the rule (first non-blank line is exactly the marker). An activity edited to or from Hevy text is simply re-parsed, and its old sets are removed. Rejected: also classifying with `LIKE` in SQL (two rules that could disagree).

**D33. Re-parse when the raw version differs from the one parsed (`parsed_fetched_at <> source_fetched_at`) or `PARSER_VERSION` changed.**
Why: an exact comparison, independent of clocks. The first version compared `fetched_at` (the sync's clock) with `parsed_at` (the database clock); tests with fixed times exposed it. Bumping `PARSER_VERSION` replays all of history from `raw`, which is the point of ELT. Rejected: re-parsing everything every run; clock comparison.

**D34. Seeds are CSV files upserted on every run, and sport types missing from the CSV are added as `other`.**
Why: editing a CSV takes effect on the next run without a migration, and an unexpected Strava sport type never breaks the load. Rejected: seeding inside a migration (every change would need a new one).

**D35. Weights are parsed as `Decimal`, and pounds are converted with the exact factor 0.45359237.**
Why: the golden total is exact (3490.8973504 kg), with no float rounding. Rejected: floats.

**D36. Cycling maps to a new `Cardio` muscle group.** Why: it appears in Hevy sessions (sample 02) and is not a muscle. Rejected: leaving it `Unmapped` (a permanent DQ warning).

## Slice 5: marts, streak, data quality

**D37. Daily nutrition is a function over a date range (`mart.fn_daily_nutrition(p_from, p_to)`), not a view.**
Why: days with no calories must still appear as `not_logged`, which needs a date range to build the days from (`core.dim_date`). Rejected: a view over sampled days only (missing days would be guessed in the API).

**D38. The streak is two SQL functions: `fn_day_status` labels each day, `fn_streak` counts the chain containing today.**
Why: the single-freeze rule only needs "did the previous day qualify?" (`LAG`), and chains are gaps-and-islands (a running `SUM` of missed days). All 17 scenarios from ARCHITECTURE 8.4 run as tests; removing the "previous day qualified" condition fails them. Rejected: computing the streak in Python (the rule would not be testable in the database or reusable by any client).

**D39. A failing data-quality check is a stored finding, not a failed DAG run; thresholds live in each check's SQL.**
Why: "Strava is stale" must stay visible in `ops.dq_results` without hiding real pipeline errors among red DAG runs, and one file holds both the rule and its limits. `ops.dq_results` stores `status` (pass/warn/fail) only; the spec's separate `severity` column was dropped as redundant. Rejected: failing the DAG on any warning; a Python threshold table separate from the SQL.

**D40. `data_quality` runs at minute 30, after `strava_sync` (minute 0).**
Why: `row_reconcile` compares raw and core, which are only equal after the sync's transform has run. Rejected: running both on the hour.

## Slice 6a: API and dashboard

**D41. The recovery card's state is a SQL function (`mart.fn_recovery_state`), and `POST /recovery` accepts only what it calls `available`.**
Why: the card and the endpoint share one rule, so the button can never offer something the server refuses. Rejected: computing the state in Python next to a separate validation in the endpoint.

**D42. The dashboard is composed in Python from the mart functions; only display text (greeting, streak message) is decided there.**
Why: the rules stay in SQL and are tested there; the API adds wording and shapes one payload for the page. Rejected: one large SQL query returning the whole payload (hard to read and to change).

**D43. "Today" comes from `APP_TIMEZONE`; `app.profile.timezone` is stored and shown read-only in v1.**
Why: UI_SPEC 6.3 makes the time zone read-only for now, and both say Asia/Manila. Editing the time zone later means switching the clock to read the profile. Rejected: reading the profile from the database on every clock call.

**D44. Validation errors from query parameters and bodies use the standard error shape (`invalid_payload`).**
Why: the web app handles one error format everywhere. Rejected: FastAPI's default `{"detail": [...]}`.

## Plan, process, and cross-cutting

**D45. No deadlines or time gates.** (Rob, 2026-10-20.)
Milestone dates, slice date ranges, the Airflow timebox, the capacity assumption, and early-warning checkpoints were removed; M1/M2 and the priority order remain as ordering. Why: Rob wants to build as much as he can without schedule pressure. Rejected: the original Oct 31 / Nov 13 milestones.

**D46. Rob runs every git command; one branch per slice (`slice-N-short-name`), except Slices 0 and 1, which shared `slice-1-foundation`.**
The agent never runs git writes; it suggests conventional commit messages at each checkpoint, warns about secrets via `git status`, and names the next slice's branch when a slice wraps up. Slices merge to `main` through pull requests. Why: Rob keeps full control of history (CLAUDE.md). Rejected: the agent committing.

**D47. Scope moves agreed during planning (Rob, 2026-10-20).**
`v_streak` became `fn_streak(p_today)`; `GET /pipeline/health` moved from Slice 5 to 6b; DQ checks staged 5 (M1) then 15 (M2); Slice 6a ships a minimal targets form and only 3 screenshot scenarios at iPhone size; weight trend vs goal moved from Backlog to Next as the first Slice 7b item. Why: keep M1 small and finishable without dropping tests or data quality. Rejected: building all of these in their original slices.

**D48. CI runs `make -k check` (keep going).**
Why: with plain `make`, the first failing step stopped the run, so a broken API test hid the pipeline and web results. `-k` reports every failure in one run and still fails the job. Proven locally: a deliberately failing test makes `make check` exit 2. Rejected: plain `make check`.

**D49. ELT stays, re-checked against the real data (2026-10-20).**
Why: the Hevy text format kept evolving (four set kinds found in samples), so keeping `raw` lets a parser fix replay history without re-calling Strava. Precisely: "ELT with validation at ingest for pushed data, and location fields dropped before landing" (D24, D26). Rejected: ETL (anything the parser misread would be lost).

**D50. Strava is polled hourly; the app never calls Strava when it opens.**
Why: the dashboard stays fast and works when Strava is down, Airflow stays the only Strava caller, and correctness does not depend on timing (an activity's day comes from its own start time). Cost today: about 145 of 1,000 daily read calls. Deferred to the Backlog: skipping night hours, re-checking the lookback once a day, "sync if stale" on app open through Airflow's REST API, a Sync now button, and a Sync Health button (`shortcuts://run-shortcut`); Strava webhooks are evaluated in Slice 8 (they need a public URL). Rejected: pulling from Strava on app open.

**D51. Strava scope is `activity:read_all`, and tokens live only in `ops.oauth_tokens`.**
Why: Hevy sessions may be "Only You", which `activity:read` cannot see; tokens never pass through XCom or logs. Acceptable for local development; revisit encryption for hosting (Slice 8). Rejected: `activity:read`.

**D52. Real random values for `API_KEY` and `AIRFLOW_ADMIN_PASSWORD` (`openssl rand -hex 16`); `POSTGRES_PASSWORD` stays the placeholder for now.**
Why: Postgres fixes its password when the volume is first created, so changing it in `.env` alone would lock the API and Airflow out; it only listens on `127.0.0.1:5433`. Changing it later needs `ALTER USER` plus `WAREHOUSE_URL`. Rejected: sharing one placeholder across all three.

**D53. Slice 0 spike scripts use only the Python standard library; raw output goes to a gitignored `spike_out/`; committed samples are redacted.**
Strava samples keep an allowlist of fields with a fake id; Health samples replace the real weight with a made-up exact pound conversion. Why: real personal data never reaches git, and the spikes need no setup. Rejected: committing raw responses.

**D54. Re-parsing an activity deletes its open quarantine rows and writes them again; resolved rows are kept.**
Why: quarantine stays one row per real problem instead of growing on every re-parse, while human-resolved history is never lost. Rejected: appending on every parse.

**D55. A shareable "Health Push" Shortcut is deferred to the Backlog.**
Plan: an iCloud link (or a signed `.shortcut` via macOS `shortcuts sign`) with import questions for server URL and API key, never containing Rob's key. Why: the app has one user today; multi-user onboarding is out of scope. Rejected: building it now.

**D56. Every key test is proven by breaking the code on purpose before it is trusted.**
Examples: the DAG import test (a broken DAG must fail it), new-before-loaded ordering (D21), per-(date, type) replace (D1), `NULLS NOT DISTINCT` (D6), the freeze rule (D38), location dropping (D24), the reserved `run_id` name, and `make check` failing on a failing test (D48). Why: a passing test proves nothing until it has been seen to fail. Rejected: trusting green tests by default.

**D57. Interview notes are compiled in `docs/INTERVIEW_NOTES.md` after every slice, listing built work only.**
Why: the resume claims must stay honest and talking points should not be lost in chat. Rejected: notes only in chat.

**D58. Spec decisions resolved from Slice 0 and settled defaults.**
Sample order from the Shortcut is not stable (handled by D30); `source` is always present (`MyNetDiary`); weights arrive as exact pound conversions (D2); Strava's HIIT sport type is `HighIntensityIntervalTraining`; `data_quality` and every new DAG start paused and must be switched on in the Airflow UI.
