# Every command runs in Docker, so the host only needs Docker and make.
# CI runs `make check`, exactly like local.

COMPOSE := docker compose
# `run --build` rebuilds the image first if a Dockerfile or dependency changed.
RUN := $(COMPOSE) run --rm --build
RUFF := docker run --rm -v "$(CURDIR)":/io -w /io ghcr.io/astral-sh/ruff:0.16.10
GITLEAKS := docker run --rm -v "$(CURDIR)":/repo ghcr.io/gitleaks/gitleaks:v8.30.1

.PHONY: up down logs migrate strava-auth seed-demo demo-reseed check-demo-clock test test-api test-pipeline test-web lint typecheck check screenshots db-reset secret-scan check-bundle

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

# Build the demo database and load one scenario: make seed-demo SCENARIO=at_risk
# (default midweek). Then open http://localhost:5174: it starts a demo visit by itself.
seed-demo:
	$(DEMO) run --rm --build demo-seed python /scripts/seed_demo.py setup
	$(DEMO) up -d --build --renew-anon-volumes --force-recreate --wait api-demo web-demo
	$(DEMO) run --rm demo-seed python /scripts/seed_demo.py load $(or $(SCENARIO),midweek)

# Rebuild the demo's data in place (idempotent; what the demo service does at start).
demo-reseed:
	$(DEMO) run --rm demo-seed python /scripts/seed_demo.py load $(or $(SCENARIO),midweek)

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

# Leak checks (docs/AUTH_SPEC.md section 11). secret-scan: every commit in the history,
# then uncommitted changes to tracked files (new files are scanned once staged, by the
# pre-commit hook). Findings print as REDACTED. check-bundle: no secret in the web build.
secret-scan:
	$(GITLEAKS) git --config /repo/.gitleaks.toml --redact /repo
	$(GITLEAKS) git --pre-commit --config /repo/.gitleaks.toml --redact /repo

check-bundle:
	$(RUN) --no-deps web sh scripts/check-bundle.sh

check: lint typecheck test secret-scan check-bundle check-demo-clock

# The demo's clock must never be frozen by default (D124).
check-demo-clock:
	sh scripts/check_demo_clock.sh

# iPhone-size screenshots of each scenario into docs/screenshots/ (UI_SPEC.md 11). The
# demo's clock is frozen at Sat 2026-10-17 14:00 for the pictures only; afterwards the
# demo is back on the real time with the midweek story loaded (D124).
FROZEN := DEMO_NOW_OVERRIDE=2026-10-17T14:00:00+08:00
# One spec file at a time, with a minute between them on midweek (the only scenario the
# tour and the explainer run on): every test reaches the demo API from one address, and
# together they would set off its rate limit of 120 reads a minute (app/security.py).
SPECS := e2e/screenshots.spec.ts e2e/tour.spec.ts e2e/streak-explainer.spec.ts

screenshots:
	$(FROZEN) $(DEMO) up -d --build --renew-anon-volumes --force-recreate --wait api-demo web-demo
	$(DEMO) build screenshots demo-seed
	for scenario in $(SCENARIOS); do \
	  $(DEMO) run --rm demo-seed python /scripts/seed_demo.py setup && \
	  $(FROZEN) $(DEMO) run --rm demo-seed python /scripts/seed_demo.py load $$scenario && \
	  for spec in $(SPECS); do \
	    $(DEMO) run --rm -e SCENARIO=$$scenario screenshots npx playwright test $$spec || exit 1; \
	    if [ $$scenario = midweek ]; then sleep 61; fi; \
	  done; \
	done
	$(DEMO) up -d --force-recreate --wait api-demo
	$(DEMO) run --rm demo-seed python /scripts/seed_demo.py load midweek

# Destructive: deletes the Postgres volume (all local data). Ask Rob first.
db-reset:
	@echo "This deletes ALL local data in Postgres."
	@read -p "Type 'delete' to continue: " answer && [ "$$answer" = "delete" ]
	$(COMPOSE) down -v
