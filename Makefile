# Every command runs in Docker, so the host only needs Docker and make.
# CI runs `make check`, exactly like local.

COMPOSE := docker compose
# `run --build` rebuilds the image first if a Dockerfile or dependency changed.
RUN := $(COMPOSE) run --rm --build
RUFF := docker run --rm -v "$(CURDIR)":/io -w /io ghcr.io/astral-sh/ruff:0.16.10

.PHONY: up down logs migrate seed-demo test test-api test-pipeline test-web lint typecheck check screenshots db-reset

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

migrate:
	$(RUN) api alembic -c /db/alembic.ini upgrade head

seed-demo:
	@echo "seed-demo arrives in Slice 6a."; exit 1

test: test-api test-pipeline test-web

test-api:
	$(RUN) api pytest

test-pipeline:
	$(RUN) --no-deps airflow python -m pytest -p no:cacheprovider /opt/airflow/tests

test-web:
	$(RUN) --no-deps web npm test

lint:
	$(RUFF) check .
	$(RUFF) format --check .
	$(RUN) --no-deps web npm run lint

typecheck:
	$(RUN) --no-deps web npm run build

check: lint typecheck test

screenshots:
	@echo "screenshots arrive in Slice 6a."; exit 1

# Destructive: deletes the Postgres volume (all local data). Ask Rob first.
db-reset:
	@echo "This deletes ALL local data in Postgres."
	@read -p "Type 'delete' to continue: " answer && [ "$$answer" = "delete" ]
	$(COMPOSE) down -v
