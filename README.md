# fitness-tracker

*"My training, running and nutrition data lives in separate apps that don't talk to each other, so I built a pipeline that joins them."*

Strava activities (pulled by Airflow) and Apple Health nutrition data (pushed by an iOS Shortcut) land in a PostgreSQL warehouse, and a mobile-first web app shows the results. Design docs: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md), [docs/DECISIONS.md](docs/DECISIONS.md).

## Quickstart (local)

Needs only **Docker Desktop** and **make**.

```bash
cp .env.example .env      # then fill in the Strava keys
make up                   # build and start postgres, api, airflow, web
make migrate              # create the warehouse schemas
make strava-auth          # once: authorize Strava (follow the prompts)
make check                # lint, typecheck, and all tests (same as CI)
```

| Service | URL |
|---|---|
| Web app | http://localhost:5173 (on the iPhone: `http://<mac-lan-ip>:5173`) |
| API health | http://localhost:8000/api/v1/health |
| Airflow UI | http://localhost:8080 (login: `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` from `.env`) |
| Postgres | `127.0.0.1:5433`, databases `app` and `airflow` |

Open the web app and sign in: with Google (`AUTH_MODE=google`, see below), or locally with `DEV_LOGIN_KEY` from `.env` (`AUTH_MODE=key`, dev only). Then set a calorie budget and protein goal on the Me page.

## Demo and screenshots

A separate demo stack (its own database `app_demo`, clock frozen at Sat 2026-10-17 14:00) never touches real data; opening it starts a read-only demo visit (see Demo mode below).

```bash
make seed-demo SCENARIO=midweek   # or at_risk, edge_empty; then open http://localhost:5174
make screenshots                  # iPhone and desktop screenshots of every scenario into docs/screenshots/
```

| Dashboard | Activities | Nutrition | Me (data and sync) |
|---|---|---|---|
| ![dashboard](docs/screenshots/midweek-iphone.png) | ![activities](docs/screenshots/midweek-activities-iphone.png) | ![nutrition](docs/screenshots/midweek-nutrition-iphone.png) | ![me](docs/screenshots/midweek-me-iphone.png) |

Other scenarios: [at risk](docs/screenshots/at_risk-iphone.png), [stale pipeline](docs/screenshots/at_risk-me-iphone.png), [nothing set up yet](docs/screenshots/edge_empty-iphone.png), [desktop](docs/screenshots/midweek-desktop.png), [trends by month](docs/screenshots/midweek-activities-month-iphone.png), [weights in pounds](docs/screenshots/midweek-nutrition-lb-iphone.png).

Other commands: `make down`, `make logs`, `make test`, `make lint`. `make db-reset` deletes all local data.

## Demo mode

The launch screen's **Demo version** button opens a separate demo service with synthetic data. How it is isolated:

- **Its own service and database.** The demo API runs with `APP_ENV=demo` against `app_demo` only. Its one database role, `demo_reader`, can SELECT there and cannot even connect to the real warehouse (CONNECT is revoked from PUBLIC on `app` and `airflow`).
- **No real secrets.** It starts without `.env`. The startup guard refuses to run if any `GOOGLE_*`, `OAUTH_*`, `INGEST_TOKEN*`, `STRAVA_*`, `AIRFLOW_*`, `POSTGRES_*` or dev-key variable is set, or if the database name doesn't end in `_demo`.
- **A demo visit, not a sign-in.** Opening the demo sets a signed, 2-hour `demo_session` cookie (its own secret, no database row). The real app never reads it, and the demo never reads real sessions.
- **Read-only, on the server.** Every write gets `403 demo_read_only` ("Demo mode: changes aren't saved."), and the sign-in, ingest and sync routes don't exist there. The database role refuses writes too.
- **Limits:** 10 new visits and 120 reads a minute per address; bodies over 1 KB are refused.
- **Built by the pipeline, not inserted.** The demo's data is synthetic Strava activity details (with Hevy text) and Shortcut batches, replayed through the real sync, Hevy parser, core load, ingest checks and the 15 data-quality checks. It includes the mess a real pipeline meets: unreadable set lines in quarantine, an unmapped exercise, a duplicate push, a timed-out sync and its retry. The seed is fixed and days count back from today, so the demo shows the same story on any date; a daily GitHub Actions job rebuilds it in one transaction (about 4 seconds, 11 MB), so visitors never see it half-built, and a visit to day-old data asks for a rebuild. The demo service itself holds only the read-only role.
- **Try your own settings.** On the demo's Me page you can change the calorie budget, protein goal, weight goal and weekend rule; every page follows, for every day. The settings stay in your browser tab, ride along with each request, and are applied inside that request's database transaction only. Nothing is saved; **Reset demo** puts the demo's own back.
- **A guided tour** spotlights each card and names where its data comes from: the real tables, SQL functions, Airflow DAGs and tasks, and endpoints. The steps are a data file (`web/src/tour/steps.json`), and a test checks every name against the code.

## Authentication and security

Full design: [docs/AUTH_SPEC.md](docs/AUTH_SPEC.md). The app has one user, so the goal is defense in depth: no single mistake (a leaked log, a committed file, a stolen cookie, a wrong setting) should expose the data or a credential.

- **Sign-in:** Google (OpenID Connect, with PKCE, a nonce and a single-use state) for exactly one Google account, matched on its stable `sub` and checked on every request. Nothing from Google is stored: no email, no tokens.
- **Sessions:** a random 256-bit id in an HttpOnly, SameSite=Lax cookie (`__Host-` and Secure in production). The database keeps only its SHA-256, so a database copy cannot be turned into a cookie. 60 days at most, 30 idle.
- **The iOS Shortcut** has its own token, valid on the ingest route only. The server keeps only its hash, and rotation is supported.
- **CSRF:** requests that change something must come from the app's own `Origin` and be JSON. No CORS.
- **Hardening:** strict Content-Security-Policy and security headers, no-store caching, HSTS and no API docs in production, startup guards that refuse an unsafe configuration, rate limits on sign-in and ingest, credential redaction in logs.
- **Proof in CI:** a test that every route is public on purpose or guarded, a fake Google that tries wrong audiences, issuers, nonces, keys, states and PKCE verifiers, a log and response leak test with canary secrets, a bundle check, and gitleaks over the full git history.

**Residual risks** (what this design does not protect against):
- Someone who takes over the allowed Google account. Mitigation: a passkey or 2-step verification on that account.
- A compromise of the host or of its secret store.
- Someone using the owner's unlocked phone, where the Shortcut's token can be read.

