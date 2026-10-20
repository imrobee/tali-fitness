"""Migration 0003 removes location data from Strava rows landed before DECISIONS D24."""

import json
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ALEMBIC_INI = "/opt/airflow/db/alembic.ini"
TEST_DATABASE = "migration_0003_test"


@pytest.fixture
def database_at_0002():
    """A fresh database migrated only up to 0002, so 0003 can be applied in the test."""
    server_url = make_url(os.environ["WAREHOUSE_URL"])
    admin = create_engine(server_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS migration_0003_test WITH (FORCE)"))
        conn.execute(text("CREATE DATABASE migration_0003_test"))

    url = server_url.set(database=TEST_DATABASE)
    config = Config(ALEMBIC_INI)
    config.set_main_option(
        "sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%")
    )
    command.upgrade(config, "0002")
    engine = create_engine(url)

    yield engine, config

    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS migration_0003_test WITH (FORCE)"))
    admin.dispose()


def test_upgrade_removes_location_fields_and_keeps_the_rest(database_at_0002):
    engine, config = database_at_0002
    payload = {
        "id": 7,
        "description": "Logged with hevyapp.com",
        "start_latlng": [1.0, 2.0],
        "end_latlng": [1.1, 2.1],
        "map": {"polyline": "fake"},
        "segment_efforts": [{"segment": {"city": "Faketown"}}],
    }
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO raw.strava_activities (strava_id, payload, fetched_at) "
                "VALUES (7, CAST(:payload AS jsonb), now())"
            ),
            {"payload": json.dumps(payload)},
        )

    command.upgrade(config, "0003")

    with engine.connect() as conn:
        stored = conn.execute(text("SELECT payload FROM raw.strava_activities")).scalar_one()
    assert stored == {"id": 7, "description": "Logged with hevyapp.com"}
