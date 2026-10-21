"""Shared fixtures: a throwaway warehouse database migrated to the latest schema.

Runs inside the Airflow container against the real Postgres service (`make test-pipeline`).
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

ALEMBIC_INI = "/opt/airflow/db/alembic.ini"
TEST_DATABASE = "pipeline_test"


@pytest.fixture(scope="session")
def migrated_engine():
    """Create pipeline_test, run every migration once, drop it after the test session."""
    server_url = make_url(os.environ["WAREHOUSE_URL"])
    # CREATE/DROP DATABASE cannot run inside a transaction, hence AUTOCOMMIT.
    admin = create_engine(server_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS pipeline_test WITH (FORCE)"))
        conn.execute(text("CREATE DATABASE pipeline_test"))

    url = server_url.set(database=TEST_DATABASE)
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
        conn.execute(text("DROP DATABASE IF EXISTS pipeline_test WITH (FORCE)"))
    admin.dispose()


@pytest.fixture
def engine(migrated_engine: Engine) -> Engine:
    """The migrated database with the Strava and ops tables emptied before each test."""
    with migrated_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE raw.strava_activities, ops.oauth_tokens, ops.watermarks, "
                "ops.pipeline_runs, ops.quarantine, core.dim_exercise, "
                "core.dim_activity_type, core.exercise_muscle_map, raw.health_batches, "
                "app.recovery_day, app.target_history, ops.dq_results CASCADE"
            )
        )
    return migrated_engine
