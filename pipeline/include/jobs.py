"""The pipeline's jobs as plain functions (DECISIONS D132): the steps of a Strava sync and a
data-quality run. Two schedulers call them: the Airflow DAGs (local, one @task per step,
with Airflow's retries) and scripts/run_pipeline.py (production, from GitHub Actions).

Each step takes the run's ops.pipeline_runs id and writes its own error into that row
(runs.record_failure), so the row says what happened whichever scheduler ran it.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine

from include import runs
from include.core.activities import transform_activities
from include.core.sets import parse_pending
from include.db import load_sql
from include.dq.checks import CHECKS, run_checks
from include.strava import sync
from include.strava.client import StravaClient

# --- Strava sync: refresh_token -> sync_activities -> transform_core -> parse_hevy ---------


def refresh_token(engine: Engine, run_id: int, client: StravaClient, now: datetime) -> None:
    with runs.record_failure(engine, run_id):
        sync.ensure_fresh_token(engine, client, now=now)


def sync_activities(
    engine: Engine, run_id: int, client: StravaClient, now: datetime, backfill_days: int
) -> None:
    with runs.record_failure(engine, run_id):
        result = sync.sync_activities(engine, client, now=now, backfill_days=backfill_days)
        # 'partial' = stopped at the per-run fetch cap; the next run continues.
        status = "partial" if result.hit_cap else "success"
        with engine.begin() as conn:
            runs.finish_run(conn, run_id, status, result.listed, result.written)


def transform_core(engine: Engine, run_id: int) -> None:
    # raw.strava_activities -> core.fact_activity (all rows; upsert, so idempotent).
    with runs.record_failure(engine, run_id):
        transform_activities(engine)


def parse_hevy(engine: Engine, run_id: int) -> None:
    # Only activities that are new, re-fetched, or parsed by an older grammar.
    with runs.record_failure(engine, run_id):
        result = parse_pending(engine)
        with engine.begin() as conn:
            conn.execute(
                load_sql("ops/add_quarantined.sql"),
                {"run_id": run_id, "count": result.quarantined},
            )


# --- data quality --------------------------------------------------------------------------


def check_data(engine: Engine, run_id: int, now: datetime) -> None:
    # A failing check is a finding in ops.dq_results; only an error running them fails.
    with runs.record_failure(engine, run_id):
        results = run_checks(engine, now=now, run_id=run_id)
        with engine.begin() as conn:
            runs.finish_run(conn, run_id, "success", len(CHECKS), len(results))


# --- a whole job in one go (production: no Airflow) ----------------------------------------


@dataclass(frozen=True)
class JobResult:
    run_id: int
    ok: bool


def run_strava_sync(
    engine: Engine, client: StravaClient, now: datetime, backfill_days: int
) -> JobResult:
    """All four steps in order, like the DAG; the first error stops the rest (Airflow
    would skip them too). No retries: the next hourly run picks up where this stopped
    (the watermark). The run row is always closed, like the DAG's close_run."""
    with engine.begin() as conn:
        run_id = runs.start_run(conn, source=sync.SOURCE, airflow_run_id=None)
    try:
        refresh_token(engine, run_id, client, now)
        sync_activities(engine, run_id, client, now, backfill_days)
        transform_core(engine, run_id)
        parse_hevy(engine, run_id)
        return JobResult(run_id, ok=True)
    except Exception:
        return JobResult(run_id, ok=False)  # the error is already in the run row
    finally:
        with engine.begin() as conn:
            runs.close_run(conn, run_id)


def run_data_quality(engine: Engine, now: datetime) -> JobResult:
    """The data-quality checks, like the data_quality DAG."""
    with engine.begin() as conn:
        run_id = runs.start_run(conn, source="dq", airflow_run_id=None)
    try:
        check_data(engine, run_id, now)
        return JobResult(run_id, ok=True)
    except Exception:
        return JobResult(run_id, ok=False)
    finally:
        with engine.begin() as conn:
            runs.close_run(conn, run_id)
