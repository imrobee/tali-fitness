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

Other commands: `make down`, `make logs`, `make test`, `make lint`. `make db-reset` deletes all local data.
