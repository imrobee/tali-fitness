"""The strava_sync DAG has the settings ARCHITECTURE.md section 6.1 asks for."""

import inspect
from datetime import timedelta

import pytest
from airflow.dag_processing.dagbag import DagBag
from airflow.sdk import Context

DAGS_FOLDER = "/opt/airflow/dags"


@pytest.fixture(scope="module")
def dag():
    return DagBag(dag_folder=DAGS_FOLDER).dags["strava_sync"]


def test_runs_hourly_without_catchup_and_one_run_at_a_time(dag):
    assert dag.schedule == "@hourly"
    assert dag.catchup is False
    assert dag.max_active_runs == 1


def test_task_order(dag):
    tasks = dag.task_dict
    assert tasks["refresh_token"].upstream_task_ids == {"start_run"}
    assert tasks["sync_activities"].upstream_task_ids == {"start_run", "refresh_token"}
    assert tasks["transform_core"].upstream_task_ids == {"start_run", "sync_activities"}
    assert tasks["parse_hevy"].upstream_task_ids == {"start_run", "transform_core"}
    assert tasks["close_run"].upstream_task_ids == {"start_run", "parse_hevy"}


def test_close_run_always_runs(dag):
    assert dag.task_dict["close_run"].trigger_rule == "all_done"


def test_no_task_argument_uses_a_reserved_airflow_context_name(dag):
    # Regression: a task argument named "run_id" made every run fail before the task
    # started (2026-10-20). Airflow reserves all of its context keys as argument names.
    reserved = set(Context.__annotations__)
    for task in dag.tasks:
        arguments = set(inspect.signature(task.python_callable).parameters)
        assert not arguments & reserved, f"{task.task_id} uses {arguments & reserved}"


def test_retries_back_off_and_time_out(dag):
    sync_task = dag.task_dict["sync_activities"]
    assert sync_task.retries == 3
    assert sync_task.retry_exponential_backoff == 2.0
    assert sync_task.execution_timeout == timedelta(minutes=20)
