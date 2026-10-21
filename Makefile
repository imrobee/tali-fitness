# Every command runs in Docker, so the host only needs Docker and make.
# CI runs `make check`, exactly like local.

COMPOSE := docker compose
# `run --build` rebuilds the image first if a Dockerfile or dependency changed.
RUN := $(COMPOSE) run --rm --build
RUFF := docker run --rm -v "$(CURDIR)":/io -w /io ghcr.io/astral-sh/ruff:0.16.10

.PHONY: up down logs migrate strava-auth seed-demo test test-api test-pipeline test-web lint typecheck check screenshots db-reset

# --renew-anon-volumes: the web container keeps node_modules in an anonymous volume;
# without this flag a rebuilt image would keep the old packages. Only anonymous volumes
# are renewed: the database lives in the named volume pgdata and is never touched.
up:
	$(COMPOSE) up -d --build --renew-anon-volumes

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

migrate:
	$(RUN) api alembic -c /db/alembic.ini upgrade head

# One-time: authorize Strava and store the tokens in ops.oauth_tokens (interactive).
strava-auth:
	$(RUN) airflow python -m include.strava.auth

# Demo data lives in its own database (app_demo), never the real warehouse.
DEMO := $(COMPOSE) --profile demo
SCENARIOS := midweek at_risk edge_empty

# Load one demo scenario: make seed-demo SCENARIO=at_risk (default midweek).
# Then open http://localhost:5174 with the key "demo-key".
seed-demo:
	$(DEMO) up -d --build --renew-anon-volumes --wait api-demo web-demo
	$(DEMO) run --rm api-demo python /scripts/seed_demo.py $(or $(SCENARIO),midweek)

test: test-api test-pipeline test-web

test-api:
	$(RUN) api pytest

# Starts Postgres too: the sync tests use a throwaway database on it.
test-pipeline:
	$(RUN) airflow python -m pytest -p no:cacheprovider /opt/airflow/tests

test-web:
	$(RUN) --no-deps web npm test

lint:
	$(RUFF) check .
	$(RUFF) format --check .
	$(RUN) --no-deps web npm run lint

typecheck:
	$(RUN) --no-deps web npm run build

check: lint typecheck test

# iPhone-size screenshots of each scenario into docs/screenshots/ (UI_SPEC.md 11).
screenshots:
	$(DEMO) up -d --build --renew-anon-volumes --wait api-demo web-demo
	$(DEMO) build screenshots
	for scenario in $(SCENARIOS); do \
	  $(DEMO) run --rm api-demo python /scripts/seed_demo.py $$scenario && \
	  $(DEMO) run --rm -e SCENARIO=$$scenario screenshots npx playwright test || exit 1; \
	done

# Destructive: deletes the Postgres volume (all local data). Ask Rob first.
db-reset:
	@echo "This deletes ALL local data in Postgres."
	@read -p "Type 'delete' to continue: " answer && [ "$$answer" = "delete" ]
	$(COMPOSE) down -v
