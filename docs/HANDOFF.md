# Handoff (2026-11-04)

Where the project stands, for picking it up in a new conversation. Read with `CLAUDE.md` (working agreement), `docs/PROJECT_PLAN.md` (status per slice), and `docs/DECISIONS.md` (D1-D115).

## Where we are

- **Slices 0-7d are done and merged** (PRs #1-#10).
- **Slice 8a (Google sign-in and the ingest token) is built and green** on `slice-8a-google-auth`, waiting on Rob's checklist (AUTH_SPEC section 13). Google sign-in for one account, server-side sessions (migration 0015, applied), an Origin check, the hashed Shortcut token, hardening, leak tests, gitleaks in CI. The shared `API_KEY` works nowhere now. Departures from the spec: D109, D110, D112, D113, D115.
- Tests: 338 API + 214 pipeline + 170 web, plus the secret scan and the bundle check, all green with `make -k check`.

## What works, and how to run it

Needs Docker Desktop and make. All commands from the repo root.

```bash
make up            # start postgres, api, airflow, web
make migrate       # apply migrations (now at 0015)
make -k check      # lint, typecheck, all tests (what CI runs)
make strava-auth   # one-time Strava login (already done; only if tokens are lost)
make logs          # follow container logs
make seed-demo SCENARIO=midweek   # demo stack at http://localhost:5174, key "demo-key"
make screenshots   # docs/screenshots/{midweek,at_risk,edge_empty}-iphone.png
```

| What | Where | State |
|---|---|---|
| Web app | http://localhost:5173, iPhone `http://192.168.100.127:5173 (the Mac's address on the current Wi-Fi; check with `ipconfig getifaddr en0`)`; sign in with Google on the Mac, or with `DEV_LOGIN_KEY` in key mode (the phone in dev) | Dashboard (with weekly chart), Activities (training trend, calendar, day list filtered by a tapped day, sets on tap), Nutrition (with the calorie trend), Me (targets, data and sync) |
| API | http://localhost:8000/api/v1/health; the web routes need a signed-in session, the ingest route the Shortcut's bearer token | Working |
| Airflow UI | http://localhost:8080, login from `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` in `.env` | Working |
| Postgres | `127.0.0.1:5433`, user `fitness`, databases `app` and `airflow` | Working |

**Data flowing today:**
- **Strava:** `strava_sync` runs hourly (switched on): raw -> `core.fact_activity` -> Hevy parsed into `core.fact_set`. 24 activities; the Oct 19 session gives 22 sets / 3,490.90 kg.
- **Apple Health:** the iPhone Shortcut "Health Push" posts to `POST /api/v1/ingest/health` when MyNetDiary is closed. Calories and protein land in `core.fact_dietary_sample` from Oct 20.
- **Business rules:** `mart.fn_day_status`, `fn_streak`, `fn_daily_nutrition`, `fn_recovery_state` (streak is 1 today).
- **API endpoints:** `GET /dashboard`, `GET/PUT /me`, `POST/DELETE /recovery`, `POST /ingest/health`, `GET /pipeline/health`, `GET /activities`, `GET /activities/{id}`, `GET /calendar`, `GET /trends/training`, `GET /trends/nutrition`.

Useful queries (`docker compose exec postgres psql -U fitness -d app`):
```sql
SELECT * FROM mart.fn_streak((now() AT TIME ZONE 'Asia/Manila')::date);
SELECT * FROM ops.pipeline_runs ORDER BY run_id DESC LIMIT 10;
SELECT * FROM ops.quarantine WHERE resolved_at IS NULL;
```
Do not `SELECT *` from `ops.oauth_tokens` (it prints live Strava tokens).

## Half-finished

**Slice 7a:** built; acceptance needs Rob to open Activities (trend, calendar, tap a day) and Nutrition (calorie trend) on the iPhone with real data.

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
| Every hourly Strava run re-fetches the last 7 days | ~145 of 1,000 daily calls now; grows with activity count | Backlog (D50) |
| Streak days before Oct 20 show `missed` | Expected: calorie data starts Oct 20 | Not a bug |
| The recovery card can still grow on screens narrower than ~340px if its body wraps to three lines | Small layout shift on very small phones | UI_SPEC 5.4 |
| The design-taste inspector cannot get past the sign-in screen | Inspection uses the saved HTML from the screenshot run (`SNAPSHOT_DIR`) | D68 |
| Migration 0006 was reformatted (whitespace only) after it was applied locally | No behavior difference | Note only |

## Waiting on Rob

1. **Commit 8a** (steps 2-9) on `slice-8a-google-auth`.
2. **AUTH_SPEC section 13 checklist:** sign in with Google at http://localhost:5173 (denied the first time; copy the `sub` from `make logs` into `ALLOWED_GOOGLE_SUB`, `make up`, sign in again); try a second Google account (must be denied); put `Authorization: Bearer ing_...` in the Health Push Shortcut and run it; remove `API_KEY` from `.env` and anywhere it was pasted.
3. **iPhone in dev:** Google refuses IP-address redirect URIs, so on the phone use `AUTH_MODE=key` with `DEV_LOGIN_KEY` and `PUBLIC_BASE_URL=http://<mac-lan-ip>:5173`.
4. **"Small manual-entry forms"** (7b) still has no definition: say which forms, or drop it.

## Exact next step

After Rob's checklist and merging 8a: Slice 8 (hosting decision, deploy, README; webhooks evaluated there). Re-read `PROJECT_PLAN.md` Slice 8 first, including the auth items carried over from 8a; hosting needs Rob's approval before anything is deployed.

## Working agreements to keep

- Rob runs all git commands; suggest commit messages and the next branch name at each wrap-up (D46).
- No deadlines; push back on scope growth, naming the slice (D45).
- Verify library versions against official docs; pin releases at least two weeks old (D12).
- Prove key tests by breaking the code on purpose (D56).
- Rob prefers numbered, tap-by-tap steps for anything he does by hand, and checks his work with screenshots.
