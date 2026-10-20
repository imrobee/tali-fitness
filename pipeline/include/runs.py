"""Bookkeeping for ops.pipeline_runs: one row per DAG run.

Why each task records its own failure: Airflow 3 tasks cannot read other tasks' states
from Airflow's database, so a final "record_run" task could not tell what went wrong.
Instead the run row is opened first, each task writes its own error, and close_run
marks anything still 'running' as failed.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine

from include.db import load_sql

MAX_ERROR_LENGTH = 1000


def start_run(conn: Connection, source: str, airflow_run_id: str | None) -> int:
    row = conn.execute(
        load_sql("ops/start_run.sql"), {"source": source, "airflow_run_id": airflow_run_id}
    ).one()
    return row.run_id


def finish_run(
    conn: Connection, run_id: int, status: str, rows_read: int, rows_written: int
) -> None:
    conn.execute(
        load_sql("ops/finish_run.sql"),
        {
            "run_id": run_id,
            "status": status,
            "rows_read": rows_read,
            "rows_written": rows_written,
        },
    )


def close_run(conn: Connection, run_id: int) -> None:
    conn.execute(load_sql("ops/close_run.sql"), {"run_id": run_id})


@contextmanager
def record_failure(engine: Engine, run_id: int) -> Iterator[None]:
    """Write any error into the run row, then re-raise so Airflow still retries/fails."""
    try:
        yield
    except Exception as error:
        # Our error messages never contain tokens: they come from URLs and response bodies.
        message = f"{type(error).__name__}: {error}"[:MAX_ERROR_LENGTH]
        with engine.begin() as conn:
            conn.execute(load_sql("ops/fail_run.sql"), {"run_id": run_id, "error_message": message})
        raise
