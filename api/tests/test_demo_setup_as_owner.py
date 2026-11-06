"""The demo setup as a database owner who is not a superuser, the way Neon's owner role
is (D134). On this Mac the setup runs as a superuser, which skips Postgres's check that the
creator of a database owned by demo_seed may act as demo_seed; on Neon that check failed
("database_create.sql failed: InsufficientPrivilege", 2026-11-07)."""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.demo.setup import DemoRoles, prepare_demo_database

OWNER = "neonlike_owner"
OWNER_PASSWORD = "test-only-owner-password-0001"
DATABASE = "ownertest_demo"
REAL = "ownertest_real"  # stands in for "app", owned by the owner as on Neon
ROLES = DemoRoles(
    reader="ownertest_reader",
    reader_password="test-only-reader-password-01",
    writer="ownertest_writer",
    writer_password="test-only-writer-password-01",
)


def test_an_owner_who_is_not_a_superuser_can_set_up_the_demo_twice():
    server = make_url(os.environ["WAREHOUSE_URL"]).set(database="postgres")
    superuser = create_engine(server, isolation_level="AUTOCOMMIT")
    with superuser.connect() as conn:
        # Like Neon's owner: may create roles and databases, but is no superuser.
        conn.execute(text(f'DROP ROLE IF EXISTS "{OWNER}"'))
        conn.execute(
            text(f"CREATE ROLE \"{OWNER}\" LOGIN CREATEDB CREATEROLE PASSWORD '{OWNER_PASSWORD}'")
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{REAL}"'))
        conn.execute(text(f'CREATE DATABASE "{REAL}" OWNER "{OWNER}"'))
    owner = create_engine(
        server.set(username=OWNER, password=OWNER_PASSWORD),
        isolation_level="AUTOCOMMIT",
        hide_parameters=True,
    )
    try:
        prepare_demo_database(owner, DATABASE, ROLES, lock=[REAL])
        # Again, as after a failed or repeated setup: the roles exist now, and updating
        # them must work without superuser rights too (role_update.sql, 2026-11-07).
        prepare_demo_database(owner, DATABASE, ROLES, lock=[REAL])

        reader = create_engine(
            server.set(database=DATABASE, username=ROLES.reader, password=ROLES.reader_password)
        )
        with reader.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM demo.seed_state")).scalar_one() == 0
        reader.dispose()
        # The real database is closed to the demo roles.
        locked = create_engine(
            server.set(database=REAL, username=ROLES.reader, password=ROLES.reader_password)
        )
        try:
            locked.connect().close()
            raise AssertionError("the demo reader could open the real database")
        except Exception as error:  # psycopg's "permission denied for database"
            assert "permission denied" in str(error)
        finally:
            locked.dispose()
    finally:
        owner.dispose()
        with superuser.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{DATABASE}" WITH (FORCE)'))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{REAL}" WITH (FORCE)'))
            for role in (ROLES.reader, ROLES.writer, OWNER):
                conn.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
        superuser.dispose()


def test_a_demo_role_with_special_rights_is_refused():
    server = make_url(os.environ["WAREHOUSE_URL"]).set(database="postgres")
    superuser = create_engine(server, isolation_level="AUTOCOMMIT", hide_parameters=True)
    try:
        with superuser.connect() as conn:
            conn.execute(text(f'DROP ROLE IF EXISTS "{ROLES.writer}"'))
            conn.execute(text(f'CREATE ROLE "{ROLES.writer}" LOGIN CREATEDB'))  # widened by hand
        with superuser.connect() as conn:
            try:
                from app.demo.setup import ensure_role

                ensure_role(conn, ROLES.writer, ROLES.writer_password)
                raise AssertionError("a widened role was accepted")
            except RuntimeError as error:
                assert "special rights" in str(error)
    finally:
        with superuser.connect() as conn:
            conn.execute(text(f'DROP ROLE IF EXISTS "{ROLES.writer}"'))
        superuser.dispose()
