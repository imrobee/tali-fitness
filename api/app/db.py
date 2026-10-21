"""Database access for the API: SQLAlchemy Core with text() queries from db/sql/*.sql."""

import os
from functools import cache
from pathlib import Path

from sqlalchemy import Engine, TextClause, create_engine, text

# db/ is mounted into the api container at /db (docker-compose.yml).
SQL_DIR = Path("/db/sql")


@cache
def get_engine() -> Engine:
    """One engine (a pool of connections) for the whole app, created on first use.

    Also a FastAPI dependency, so tests can swap in an engine for a test database.
    """
    return create_engine(os.environ["WAREHOUSE_URL"])


def load_sql(name: str) -> TextClause:
    """Read a query such as "health/insert_batch.sql" from db/sql."""
    return text((SQL_DIR / name).read_text())
