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

from app import clock
from app.auth import token_hash
from app.config import Settings
from app.db import get_engine
from app.main import create_app
from app.sessions import create_session

ALEMBIC_INI = "/db/alembic.ini"
SAMPLES = Path("/samples")
# The test client signs in as this account. Obviously fake, like every test secret.
TEST_SUB = "canary-google-sub-0001"
ORIGIN = "http://testserver"  # PUBLIC_BASE_URL below: what the browser sends as Origin
# An obviously fake canary: if it ever shows up in a log or a response, a test caught a leak.
TEST_INGEST_TOKEN = "ing_canary-ingest-token-not-a-real-secret"
INGEST_HEADERS = {"Authorization": f"Bearer {TEST_INGEST_TOKEN}"}

# Tests never read .env for auth settings: the app is built from these, so a test run
# cannot depend on (or print) Rob's real values.
TEST_SETTINGS = Settings(
    app_env="test",
    auth_mode="google",
    public_base_url=ORIGIN,
    warehouse_url=SecretStr(os.environ["WAREHOUSE_URL"]),
    allowed_google_sub=TEST_SUB,
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
def anonymous(engine: Engine, monkeypatch) -> TestClient:
    """A client of the app on the test database with a frozen clock, not signed in.

    It sends the app's own Origin, as the browser does on the app's pages."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("NOW_OVERRIDE", "2026-10-20T20:00:00+08:00")
    app.dependency_overrides[get_engine] = lambda: engine
    yield TestClient(app, headers={"Origin": ORIGIN})
    app.dependency_overrides.clear()


def sign_in(client: TestClient, engine: Engine, sub: str = TEST_SUB) -> str:
    """Give the client a real session, as signing in would. Returns the session id."""
    with engine.begin() as conn:
        session_id = create_session(conn, sub, clock.now())
    client.cookies.set("session", session_id)
    return session_id


@pytest.fixture
def client(anonymous: TestClient, engine: Engine) -> TestClient:
    """The same client, signed in as the allowed account."""
    sign_in(anonymous, engine)
    return anonymous


def load_sample(name: str) -> dict:
    return json.loads((SAMPLES / name).read_text())
