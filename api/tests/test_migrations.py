"""Migrations must work on a fresh database and be safe to re-run (CLAUDE.md #6).

Each test gets an empty throwaway database on the real Postgres service.
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

ALEMBIC_INI = "/db/alembic.ini"
TEST_DATABASE = "migrations_test"
EXPECTED_SCHEMAS = {"raw", "core", "mart", "ops", "app"}


@pytest.fixture
def fresh_database_url():
    """Create an empty database, hand its URL to the test, then drop it."""
    server_url = make_url(os.environ["WAREHOUSE_URL"])
    # CREATE/DROP DATABASE cannot run inside a transaction, hence AUTOCOMMIT.
    admin = create_engine(server_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS migrations_test WITH (FORCE)"))
        conn.execute(text("CREATE DATABASE migrations_test"))

    yield server_url.set(database=TEST_DATABASE)

    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS migrations_test WITH (FORCE)"))
    admin.dispose()


def upgrade_to_head(url: URL) -> None:
    config = Config(ALEMBIC_INI)
    # The ini file is read with configparser, where "%" is special, so escape it.
    url_text = url.render_as_string(hide_password=False).replace("%", "%%")
    config.set_main_option("sqlalchemy.url", url_text)
    command.upgrade(config, "head")


def schema_names(url: URL) -> set[str]:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT schema_name FROM information_schema.schemata"))
        names = {row.schema_name for row in rows}
    engine.dispose()
    return names


def test_upgrade_creates_all_schemas_on_a_fresh_database(fresh_database_url):
    upgrade_to_head(fresh_database_url)

    assert EXPECTED_SCHEMAS <= schema_names(fresh_database_url)


def test_upgrade_twice_is_a_no_op(fresh_database_url):
    upgrade_to_head(fresh_database_url)
    upgrade_to_head(fresh_database_url)  # already at head: must not fail or change anything

    assert EXPECTED_SCHEMAS <= schema_names(fresh_database_url)
