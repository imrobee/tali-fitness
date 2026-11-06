"""Hourly data-quality checks (ARCHITECTURE.md sections 6.3 and 9).

Tasks: start_run -> run_checks -> close_run. Runs at half past each hour, after the
hourly strava_sync has finished. A failing check is stored as a finding in
ops.dq_results; only an error running the checks fails the DAG run. The check itself is
include/jobs.py, shared with the production schedule on GitHub Actions (D132).
"""

from datetime import UTC, datetime, timedelta

from airflow.sdk import TriggerRule, dag, task

from include import jobs, runs
from include.db import get_engine

DEFAULT_ARGS = {
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=10),
}


@dag(
    dag_id="data_quality",
    schedule="30 * * * *",  # minute 30 of every hour
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["dq"],
)
def data_quality():
    @task
    def start_run(**context) -> int:
        with get_engine().begin() as conn:
            return runs.start_run(conn, source="dq", airflow_run_id=context["run_id"])

    @task
    def check_data(pipeline_run_id: int) -> None:
        jobs.check_data(get_engine(), pipeline_run_id, datetime.now(UTC))

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def close_run(pipeline_run_id: int) -> None:
        with get_engine().begin() as conn:
            runs.close_run(conn, pipeline_run_id)

    pipeline_run_id = start_run()
    check_data(pipeline_run_id) >> close_run(pipeline_run_id)


data_quality()
