"""Database access for the API: SQLAlchemy Core with text() queries from db/sql/*.sql."""

from functools import cache
from pathlib import Path

from sqlalchemy import Engine, TextClause, create_engine, text
from sqlalchemy.pool import NullPool

from app.config import load_settings

# db/sql, found from this file: two folders up is the repository root on a laptop or on
# Vercel (api/app/db.py), and "/" in the container (/app/app/db.py), where db/ is
# mounted at /db (docker-compose.yml). No setting needed in either place.
SQL_DIR = Path(__file__).resolve().parents[2] / "db" / "sql"


@cache
def get_engine() -> Engine:
    """One engine (a pool of connections) for the whole app, created on first use.

    Also a FastAPI dependency, so tests can swap in an engine for a test database.
    """
    settings = load_settings()
    url = settings.warehouse_url.get_secret_value()
    if settings.vercel:
        # Serverless (D134): Neon's pooler (PgBouncer, transaction mode) pools connections,
        # so the app keeps none of its own between requests. psycopg's automatic
        # server-side prepared statements are off, so no statement outlives the
        # transaction it was prepared in, which transaction pooling can't promise.
        return create_engine(url, poolclass=NullPool, connect_args={"prepare_threshold": None})
    # pool_pre_ping checks a pooled connection before using it, so the API survives a
    # Postgres restart (or the demo database being recreated) without a failed request.
    return create_engine(url, pool_pre_ping=True)


def load_sql(name: str) -> TextClause:
    """Read a query such as "health/insert_batch.sql" from db/sql."""
    return text((SQL_DIR / name).read_text())
