"""Build the demo database and its two roles (DECISIONS D118).

Run by an administrator, never by the demo service: `scripts/seed_demo.py setup` locally,
or the same steps by hand on the host (docs/ARCHITECTURE.md section 13).

- demo_seed owns the demo database: it runs the migrations and loads the synthetic data.
- demo_reader can only SELECT in it: it is the only credential the demo API has.
- Neither can connect to the real warehouse or Airflow's database: CONNECT is revoked from
  PUBLIC there, so only their owner (and superusers) can open them.
"""

from dataclasses import dataclass

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError

from app.db import load_sql

ALEMBIC_INI = "/db/alembic.ini"


@dataclass(frozen=True)
class DemoRoles:
    reader: str
    reader_password: str
    writer: str
    writer_password: str


def require_demo_name(database: str) -> None:
    """The one guard every destructive demo step starts with."""
    if not database.endswith("_demo"):
        raise ValueError(f"Refusing to touch database {database!r}: the name must end in _demo.")


def run_built(conn: Connection, sql_file: str, params: dict) -> None:
    """Run a statement that format() built inside Postgres (DDL takes no bind parameters).

    Never logged or printed: a role statement contains a password."""
    statement = conn.execute(load_sql(sql_file), params).scalar_one()
    try:
        conn.exec_driver_sql(statement)
    except DBAPIError as error:
        # SQLAlchemy's message quotes the statement, and with it the password: report only
        # which step failed and Postgres's error class. `from None` drops the original.
        raise RuntimeError(f"{sql_file} failed: {type(error.orig).__name__}") from None


def ensure_role(conn: Connection, role: str, password: str) -> None:
    exists = conn.execute(load_sql("demo/role_exists.sql"), {"role": role}).scalar_one()
    sql_file = "demo/role_update.sql" if exists else "demo/role_create.sql"
    run_built(conn, sql_file, {"role": role, "password": password})


def database_exists(conn: Connection, database: str) -> bool:
    return conn.execute(load_sql("demo/database_exists.sql"), {"database": database}).scalar_one()


def migrate(url: URL) -> None:
    config = Config(ALEMBIC_INI)
    # The ini file is read with configparser, where "%" is special, so escape it.
    config.set_main_option(
        "sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%")
    )
    command.upgrade(config, "head")


def prepare_demo_database(admin: Engine, database: str, roles: DemoRoles, lock: list[str]) -> URL:
    """Recreate `database` empty and migrated, owned by the writer, readable by the reader,
    and lock the real databases in `lock` against both. Returns the writer's URL.

    admin: an AUTOCOMMIT engine for a role that may create roles and databases, made with
    hide_parameters=True so a failed role statement never prints a password."""
    require_demo_name(database)
    if not admin.hide_parameters:
        raise ValueError("The admin engine must hide parameters: they include passwords.")
    with admin.connect() as conn:
        ensure_role(conn, roles.writer, roles.writer_password)
        ensure_role(conn, roles.reader, roles.reader_password)
        for real in lock:
            if database_exists(conn, real):
                run_built(conn, "demo/database_lock.sql", {"database": real})
        run_built(conn, "demo/database_drop.sql", {"database": database})
        run_built(conn, "demo/database_create.sql", {"database": database, "owner": roles.writer})
        # The demo database is closed to PUBLIC too: only the two demo roles get in.
        run_built(conn, "demo/database_lock.sql", {"database": database})
        run_built(
            conn, "demo/database_grant_connect.sql", {"database": database, "role": roles.reader}
        )

    writer_url = admin.url.set(
        database=database, username=roles.writer, password=roles.writer_password
    )
    migrate(writer_url)
    writer = create_engine(writer_url, hide_parameters=True)
    with writer.begin() as conn:
        # The demo's own bookkeeping (demo.seed_state), then the reader's grants.
        conn.execute(load_sql("demo/seed_state_schema.sql"))
        conn.execute(load_sql("demo/seed_state_table.sql"))
        run_built(conn, "demo/reader_grants.sql", {"role": roles.reader})
    writer.dispose()
    return writer_url
