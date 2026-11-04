"""Shared fixtures for API tests: a migrated throwaway database and a test client."""

import json
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from app.auth import token_hash
from app.config import Settings
from app.db import get_engine
from app.main import create_app

ALEMBIC_INI = "/db/alembic.ini"
SAMPLES = Path("/samples")
TEST_API_KEY = "test-api-key"
# An obviously fake canary: if it ever shows up in a log or a response, a test caught a leak.
TEST_INGEST_TOKEN = "ing_canary-ingest-token-not-a-real-secret"
INGEST_HEADERS = {"Authorization": f"Bearer {TEST_INGEST_TOKEN}"}

# Tests never read .env for auth settings: the app is built from these, so a test run
# cannot depend on (or print) Rob's real values.
TEST_SETTINGS = Settings(
    app_env="test",
    auth_mode="google",
    public_base_url="http://testserver",
    warehouse_url=SecretStr(os.environ["WAREHOUSE_URL"]),
    ingest_token_sha256=SecretStr(token_hash(TEST_INGEST_TOKEN)),
)
app = create_app(TEST_SETTINGS)


@pytest.fixture(scope="session")
def migrated_engine():
    """Create api_test, run every migration once, drop it after the test session."""
    server_url = make_url(os.environ["WAREHOUSE_URL"])
    # CREATE/DROP DATABASE cannot run inside a transaction, hence AUTOCOMMIT.
    admin = create_engine(server_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS api_test WITH (FORCE)"))
        conn.execute(text("CREATE DATABASE api_test"))

    url = server_url.set(database="api_test")
    config = Config(ALEMBIC_INI)
    # The ini file is read with configparser, where "%" is special, so escape it.
    config.set_main_option(
        "sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%")
    )
    command.upgrade(config, "head")

    engine = create_engine(url)
    yield engine

    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS api_test WITH (FORCE)"))
    admin.dispose()


@pytest.fixture
def engine(migrated_engine: Engine) -> Engine:
    """The test database with data tables emptied (and the profile reset) before each test."""
    with migrated_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE raw.health_batches, raw.strava_activities, core.dim_activity_type, "
                "app.recovery_day, app.target_history, app.weight_goal_history, "
                "app.streak_settings_history, app.vacation, app.session, ops.quarantine, "
                "ops.pipeline_runs CASCADE"
            )
        )
        conn.execute(text("UPDATE app.profile SET nickname = NULL, weight_unit = 'kg'"))
    return migrated_engine


@pytest.fixture
def client(engine: Engine, monkeypatch) -> TestClient:
    """A client whose app talks to the test database, with a known key and a frozen clock."""
    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("NOW_OVERRIDE", "2026-10-20T20:00:00+08:00")
    app.dependency_overrides[get_engine] = lambda: engine
    yield TestClient(app)
    app.dependency_overrides.clear()


def load_sample(name: str) -> dict:
    return json.loads((SAMPLES / name).read_text())
