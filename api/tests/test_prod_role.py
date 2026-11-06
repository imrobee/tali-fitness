"""scripts/setup_prod_role.py (D115, D134): the production API's login reads and writes
rows, runs the SQL functions, and can't change the schema."""

import importlib.util

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import ProgrammingError

spec = importlib.util.spec_from_file_location("setup_prod_role", "/scripts/setup_prod_role.py")
setup_prod_role = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup_prod_role)

ROLE = "app_api_test"  # roles are server-wide: not the production name, and dropped after
PASSWORD = "test-only-password-for-app-api-0001"


@pytest.fixture
def api_login(migrated_engine: Engine):
    admin = create_engine(migrated_engine.url, hide_parameters=True)
    setup_prod_role.setup_role(admin, ROLE, PASSWORD)
    setup_prod_role.setup_role(admin, ROLE, PASSWORD)  # twice: safe to run again
    login = create_engine(migrated_engine.url.set(username=ROLE, password=PASSWORD))
    yield login
    login.dispose()
    with admin.begin() as conn:
        conn.execute(text(f'DROP OWNED BY "{ROLE}"'))  # its grants, CONNECT included
        conn.execute(text(f'DROP ROLE "{ROLE}"'))
    admin.dispose()


def test_it_can_connect_after_the_demo_locked_the_database(api_login, migrated_engine):
    # The demo setup revokes CONNECT from PUBLIC on the real database (D118).
    with migrated_engine.connect() as conn:
        database = conn.execute(text("SELECT current_database()")).scalar_one()
        conn.execute(text(f'REVOKE CONNECT ON DATABASE "{database}" FROM PUBLIC'))
        conn.commit()
    try:
        with api_login.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        with migrated_engine.connect() as conn:
            conn.execute(text(f'GRANT CONNECT ON DATABASE "{database}" TO PUBLIC'))
            conn.commit()


def test_it_reads_writes_and_runs_the_marts(api_login, engine):
    with api_login.begin() as conn:
        conn.execute(text("INSERT INTO app.recovery_day (day) VALUES ('2026-10-20')"))
        conn.execute(text("DELETE FROM app.recovery_day WHERE day = '2026-10-20'"))
        conn.execute(text("SELECT * FROM mart.fn_streak(CAST('2026-10-21' AS date))")).all()
        conn.execute(text("SELECT count(*) FROM ops.pipeline_runs")).scalar_one()


@pytest.mark.parametrize(
    "ddl",
    [
        "CREATE TABLE app.sneaky (id int)",
        "DROP TABLE app.recovery_day",
        "ALTER TABLE app.recovery_day ADD COLUMN x int",
        "CREATE TABLE public.sneaky (id int)",
    ],
)
def test_it_cannot_change_the_schema(api_login, ddl):
    with pytest.raises(ProgrammingError), api_login.begin() as conn:
        conn.execute(text(ddl))
