"""ops.pipeline_runs bookkeeping: every run ends with a final status."""

import pytest
from sqlalchemy import Engine, text

from include import runs


def run_row(engine: Engine, run_id: int):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT * FROM ops.pipeline_runs WHERE run_id = :id"), {"id": run_id}
        ).one()


def open_run(engine: Engine) -> int:
    with engine.begin() as conn:
        return runs.start_run(conn, source="strava", airflow_run_id="manual__test")


def test_a_new_run_is_running(engine):
    run_id = open_run(engine)

    row = run_row(engine, run_id)
    assert row.status == "running"
    assert row.airflow_run_id == "manual__test"


def test_a_task_error_is_written_to_the_run_and_still_raised(engine):
    run_id = open_run(engine)

    with pytest.raises(RuntimeError, match="boom"):
        with runs.record_failure(engine, run_id):
            raise RuntimeError("boom")

    row = run_row(engine, run_id)
    assert row.status == "failed"
    assert row.error_message == "RuntimeError: boom"
    assert row.finished_at is not None


def test_close_run_fails_a_run_that_never_finished(engine):
    run_id = open_run(engine)

    with engine.begin() as conn:
        runs.close_run(conn, run_id)

    row = run_row(engine, run_id)
    assert row.status == "failed"
    assert row.error_message == "run ended before the sync finished"


def test_close_run_keeps_a_finished_status(engine):
    run_id = open_run(engine)
    with engine.begin() as conn:
        runs.finish_run(conn, run_id, "success", rows_read=3, rows_written=3)
        runs.close_run(conn, run_id)

    row = run_row(engine, run_id)
    assert row.status == "success"
    assert (row.rows_read, row.rows_written) == (3, 3)


def test_close_run_keeps_the_original_error(engine):
    run_id = open_run(engine)
    with pytest.raises(RuntimeError):
        with runs.record_failure(engine, run_id):
            raise RuntimeError("token refresh failed")

    with engine.begin() as conn:
        runs.close_run(conn, run_id)

    assert run_row(engine, run_id).error_message == "RuntimeError: token refresh failed"
