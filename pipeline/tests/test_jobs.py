"""The pipeline's jobs without Airflow (include/jobs.py, DECISIONS D132): what the
production schedule on GitHub Actions runs. Same functions as the DAG tasks, so the run
rows look the same whichever scheduler ran them."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text
from strava_fakes import FakeStrava, make_activity
from test_strava_sync import seed_token

from include import jobs

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def run_rows(engine: Engine) -> list:
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT source, status, rows_read, rows_written, error_message, airflow_run_id "
                "FROM ops.pipeline_runs ORDER BY run_id"
            )
        ).all()


def activity_count(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM core.fact_activity")).scalar_one()


def test_a_strava_job_runs_every_step_and_closes_its_run(engine):
    seed_token(engine)
    client = FakeStrava([make_activity(i, NOW - timedelta(days=i)) for i in (1, 2)])

    result = jobs.run_strava_sync(engine, client, now=NOW, backfill_days=90)

    assert result.ok
    assert [(r.source, r.status, r.rows_read, r.rows_written) for r in run_rows(engine)] == [
        ("strava", "success", 2, 2)
    ]
    assert run_rows(engine)[0].airflow_run_id is None  # not run by Airflow
    assert activity_count(engine) == 2  # transform_core ran


def test_running_it_twice_adds_no_duplicates(engine):
    seed_token(engine)
    client = FakeStrava([make_activity(i, NOW - timedelta(days=i)) for i in (1, 2)])

    jobs.run_strava_sync(engine, client, now=NOW, backfill_days=90)
    jobs.run_strava_sync(engine, client, now=NOW, backfill_days=90)

    assert activity_count(engine) == 2
    assert [r.status for r in run_rows(engine)] == ["success", "success"]


def test_a_failing_step_stops_the_rest_and_the_run_says_why(engine):
    seed_token(engine)
    client = FakeStrava([make_activity(1, NOW - timedelta(days=1))], fail_on_detail=1)

    result = jobs.run_strava_sync(engine, client, now=NOW, backfill_days=90)

    assert not result.ok
    row = run_rows(engine)[0]
    assert row.status == "failed"
    assert "simulated crash" in row.error_message
    assert activity_count(engine) == 0  # transform_core never ran


def test_no_token_fails_the_run_instead_of_crashing_the_job(engine):
    result = jobs.run_strava_sync(engine, FakeStrava([]), now=NOW, backfill_days=90)

    assert not result.ok
    assert run_rows(engine)[0].status == "failed"


def test_a_data_quality_job_records_its_checks(engine):
    result = jobs.run_data_quality(engine, now=NOW)

    assert result.ok
    row = run_rows(engine)[0]
    assert (row.source, row.status) == ("dq", "success")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM ops.dq_results")).scalar_one() > 0
