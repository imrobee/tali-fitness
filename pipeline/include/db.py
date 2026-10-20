"""Database helpers shared by DAG tasks.

One way to talk to Postgres everywhere (ARCHITECTURE.md section 2): SQLAlchemy Core with
text() queries and bound parameters. The SQL itself lives in db/sql/*.sql.
"""

import os
from pathlib import Path

from sqlalchemy import Engine, TextClause, create_engine, text

# db/sql is mounted read-only into the Airflow container at this path.
SQL_DIR = Path("/opt/airflow/db/sql")


def get_engine(url: str | None = None) -> Engine:
    """Engine for the warehouse database ("app"). Tests pass their own URL."""
    return create_engine(url or os.environ["WAREHOUSE_URL"])


def load_sql(name: str) -> TextClause:
    """Read a query such as "ops/start_run.sql" from db/sql."""
    return text((SQL_DIR / name).read_text())
