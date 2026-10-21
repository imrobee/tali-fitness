# Handoff (2026-10-21)

Where the project stands, for picking it up in a new conversation. Read with `CLAUDE.md` (working agreement), `docs/PROJECT_PLAN.md` (status per slice), and `docs/DECISIONS.md` (D1-D58).

## Where we are

- **Slices 0-5 are done and merged into `main`** (PRs #1-#5).
- **Slice 6a (M1) is half done** on branch `slice-6a-api-dashboard`: the API is finished and tested; the web half has not started.
- Tests: 74 API + 126 pipeline + 2 web, all green with `make -k check`.

## What works, and how to run it

Needs Docker Desktop and make. All commands from the repo root.

```bash
make up            # start postgres, api, airflow, web
make migrate       # apply migrations (now at 0007)
make -k check      # lint, typecheck, all tests (what CI runs)
make strava-auth   # one-time Strava login (already done; only if tokens are lost)
make logs          # follow container logs
```

| What | Where | State |
|---|---|---|
| Web app (Slice 1 placeholder page only) | http://localhost:5173, iPhone `http://192.168.100.120:5173` | Shows "API is up" |
| API | http://localhost:8000/api/v1/health; every other endpoint needs `X-API-Key` (value in `.env`) | Working |
| Airflow UI | http://localhost:8080, login from `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` in `.env` | Working |
| Postgres | `127.0.0.1:5433`, user `fitness`, databases `app` and `airflow` | Working |

**Data flowing today:**
- **Strava:** `strava_sync` runs hourly (switched on): raw -> `core.fact_activity` -> Hevy parsed into `core.fact_set`. 24 activities; the Oct 19 session gives 22 sets / 3,490.90 kg.
- **Apple Health:** the iPhone Shortcut "Health Push" posts to `POST /api/v1/ingest/health` when MyNetDiary is closed. Calories and protein land in `core.fact_dietary_sample` from Oct 20.
- **Business rules:** `mart.fn_day_status`, `fn_streak`, `fn_daily_nutrition`, `fn_recovery_state` (streak is 1 today).
- **API endpoints:** `GET /dashboard`, `GET/PUT /me`, `POST/DELETE /recovery`, `POST /ingest/health`.

Useful queries (`docker compose exec postgres psql -U fitness -d app`):
```sql
SELECT * FROM mart.fn_streak((now() AT TIME ZONE 'Asia/Manila')::date);
SELECT * FROM ops.pipeline_runs ORDER BY run_id DESC LIMIT 10;
SELECT * FROM ops.quarantine WHERE resolved_at IS NULL;
```
Do not `SELECT *` from `ops.oauth_tokens` (it prints live Strava tokens).

## Half-finished

**Slice 6a, web half (not started):**
1. Pin new web libraries after checking their docs (CLAUDE.md #7): `react-router`, `@tanstack/react-query`, `react-icons`, `@testing-library/react`, `jsdom`, Playwright. Pick releases at least two weeks old (D12) and record each in DECISIONS.
2. App shell: bottom navigation with 4 tabs (Dashboard, Activities, Nutrition, Me), `?date=` shared state, API-key gate (key in `localStorage`; a 401 returns to the gate), dark tokens in `web/src/theme/tokens.css` (UI_SPEC 1, 7).
3. Dashboard cards from greeting through protein (UI_SPEC 2, 5.1-5.7): greeting, day chooser, streak card, recovery card, logged exercises card, calorie ring, protein card. Pure functions (ring math, formatting) with Vitest tests.
4. Me page: targets form (`PUT /me`, limits 800-6000 kcal and 0-400 g), nickname, read-only time zone, masked API key.
5. Activities and Nutrition pages: minimal placeholders.
6. Screenshots: a separate demo database and demo API with `APP_ENV=test` and `NOW_OVERRIDE`, so demo data never touches the real warehouse; `scripts/seed_demo.py --scenario midweek|at_risk|edge_empty`; `make screenshots` with Playwright at 393x852 into `docs/screenshots/`; `make seed-demo` and `make screenshots` are placeholders today.
7. Check `UI_SPEC.md` section 12 items for these cards; Rob opens it on the iPhone with real data.
8. Wrap up: docs, DECISIONS, Interview notes into `docs/INTERVIEW_NOTES.md`, mark 6a done, next branch `slice-6b-pages`.

**Also open:** the `data_quality` DAG exists but is paused in Airflow, so `ops.dq_results` is still empty.

## Known bugs and limitations

| Issue | Impact | Where tracked |
|---|---|---|
| Deleting the *last* food entry of a type on a day does not propagate to the warehouse | That day keeps the old value until another entry of that type is logged | D1 |
| Strava edits older than 7 days before the newest activity are not re-read | Rare; old descriptions stay as first loaded | ARCHITECTURE 6.1 |
| Strava deletions are not reconciled | A deleted activity stays in the warehouse | Backlog |
| A stray non-`Set` line in Hevy text would be read as an exercise name | Hevy never writes such lines today | ARCHITECTURE 7 |
| Decimal distances and miles in Hevy text are quarantined, not parsed | Not seen in real data yet | ARCHITECTURE 7 |
| Health pushes fail when the iPhone is off home Wi-Fi or the Mac is asleep | The next push fills the gap (each batch covers yesterday and today) | D5, Slice 8 hosting |
| The Shortcut cannot read Health data while the iPhone is locked | Why the trigger is "MyNetDiary closed" | D5 |
| `StarletteDeprecationWarning` in API tests (TestClient wants `httpx2`) | Warning only | Revisit before upgrading FastAPI |
| Every hourly Strava run re-fetches the last 7 days | ~145 of 1,000 daily calls now; grows with activity count | Backlog (D50) |
| Streak days before Oct 20 show `missed` | Expected: calorie data starts Oct 20 | Not a bug |
| Migration 0006 was reformatted (whitespace only) after it was applied locally | No behavior difference | Note only |

## Waiting on Rob

1. **Commit the Slice 6a API checkpoint** if not done yet. Check `git status`; expected untracked/modified: `api/app/dashboard/`, `api/app/me.py`, `api/app/recovery.py`, `api/app/main.py`, `api/tests/`, `db/migrations/versions/0007_profile_recovery_state.py`, `db/sql/api/`, `docs/`. Suggested message: `feat: add dashboard, me, and recovery endpoints`. Leave out `.agents/`, `.claude/skills/`, `skills-lock.json` (skill install).
2. **Switch on `data_quality`** in the Airflow UI.
3. **Confirm CI test counts**: `gh auth login` so the agent can read Actions logs, or paste the "passed" lines from the latest run (expect 74 / 126 / 2 after this checkpoint).
4. Optional: delete the old `slice-1-foundation` branch; change `POSTGRES_PASSWORD` (needs `ALTER USER`, see D52).
5. After the web half: open the app on the iPhone and set nickname and targets on the Me page.

## Exact next step

On branch `slice-6a-api-dashboard`, after the checkpoint commit: start the **web half of Slice 6a**, step 1 above. Verify the docs and two-week-old versions for `react-router`, `@tanstack/react-query`, `react-icons`, `@testing-library/react`, `jsdom`, and Playwright, then build the app shell (bottom navigation, `?date=` state, API-key gate, dark tokens) with tests. Re-read `UI_SPEC.md` sections 1-5, 7-12 and `ARCHITECTURE.md` section 11 first; the dashboard payload shape there is now implemented in `api/app/dashboard/models.py`.

## Working agreements to keep

- Rob runs all git commands; suggest commit messages and the next branch name at each wrap-up (D46).
- No deadlines; push back on scope growth, naming the slice (D45).
- Verify library versions against official docs; pin releases at least two weeks old (D12).
- Prove key tests by breaking the code on purpose (D56).
- Rob prefers numbered, tap-by-tap steps for anything he does by hand, and checks his work with screenshots.
