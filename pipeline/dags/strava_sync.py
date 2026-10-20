"""Hourly Strava sync into raw.strava_activities (ARCHITECTURE.md section 6.1).

Tasks: start_run -> refresh_token -> sync_activities -> close_run.
The logic lives in include/ so it can be tested without Airflow; these tasks only wire
it together. No token ever passes through XCom: refresh_token saves it in
ops.oauth_tokens and sync_activities reads it from there.
"""

import os
from datetime import UTC, datetime, timedelta

from airflow.sdk import TriggerRule, dag, task

from include import runs
from include.db import get_engine
from include.strava import sync
from include.strava.client import StravaClient

DEFAULT_ARGS = {
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    # In Airflow 3.3 this is a multiplier (0 = constant delay): waits of 2, 4, 8 minutes.
    "retry_exponential_backoff": 2.0,
    "max_retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(minutes=20),
}


@dag(
    dag_id="strava_sync",
    schedule="@hourly",
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,  # never queue up missed hours; the watermark already covers the gap
    max_active_runs=1,  # two overlapping syncs would fetch the same activities twice
    default_args=DEFAULT_ARGS,
    tags=["strava"],
)
def strava_sync():
    @task
    def start_run(**context) -> int:
        with get_engine().begin() as conn:
            return runs.start_run(conn, source=sync.SOURCE, airflow_run_id=context["run_id"])

    # Our run-row id is called pipeline_run_id: "run_id" is reserved for Airflow's own
    # run context, and a task argument with that name fails before the task starts.
    @task
    def refresh_token(pipeline_run_id: int) -> None:
        engine = get_engine()
        with runs.record_failure(engine, pipeline_run_id):
            sync.ensure_fresh_token(engine, StravaClient.from_env(), now=datetime.now(UTC))

    @task
    def sync_activities(pipeline_run_id: int) -> None:
        engine = get_engine()
        with runs.record_failure(engine, pipeline_run_id):
            result = sync.sync_activities(
                engine,
                StravaClient.from_env(),
                now=datetime.now(UTC),
                backfill_days=int(os.environ["BACKFILL_DAYS"]),
            )
            # 'partial' = stopped at the per-run fetch cap; the next run continues.
            status = "partial" if result.hit_cap else "success"
            with engine.begin() as conn:
                runs.finish_run(conn, pipeline_run_id, status, result.listed, result.written)

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def close_run(pipeline_run_id: int) -> None:
        # Runs even when an earlier task failed, so every run ends with a final status.
        with get_engine().begin() as conn:
            runs.close_run(conn, pipeline_run_id)

    pipeline_run_id = start_run()
    refreshed = refresh_token(pipeline_run_id)
    synced = sync_activities(pipeline_run_id)
    refreshed >> synced >> close_run(pipeline_run_id)


strava_sync()
