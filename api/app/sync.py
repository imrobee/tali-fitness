"""POST /api/v1/sync/strava ("Sync now") and GET /api/v1/sync/strava (its progress).

Two ways to start a Strava sync now (DECISIONS D78, D133):
- production: ask GitHub Actions to run the pipeline workflow (PIPELINE_DISPATCH_TOKEN),
  the same job the hourly schedule runs; its progress is the run row it writes in
  ops.pipeline_runs;
- local: ask Airflow to run the strava_sync DAG (AIRFLOW_URL), and follow Airflow's run.
Guards either way: one request per 2 minutes, and none while a Strava run is in progress.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated

import httpx2
from fastapi import APIRouter, Depends
from pydantic import BaseModel, SecretStr
from sqlalchemy import Engine

from app import clock
from app.airflow import AirflowClient, AirflowError, get_airflow
from app.auth import require_user
from app.config import Settings, get_settings
from app.db import get_engine, load_sql
from app.errors import ApiError
from app.github import dispatch_workflow

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])

DAG_ID = "strava_sync"
WORKFLOW = "pipeline.yml"
COOLDOWN = timedelta(minutes=2)
# A pipeline run's status, as the page shows it (partial: stopped at the fetch cap, which
# still brought new activities in).
RUN_STATES = {"running": "running", "success": "success", "partial": "success", "failed": "failed"}


class SyncStatus(BaseModel):
    requested_at: datetime | None
    # The request being followed: Airflow's dag_run_id, or "github-<request id>".
    dag_run_id: str | None
    state: str | None  # queued | running | success | failed; None before any request


@dataclass(frozen=True)
class GitHubSync:
    repo: str
    token: SecretStr
    transport: httpx2.BaseTransport | None = None  # a fake GitHub, in tests


def get_github_sync(settings: Annotated[Settings, Depends(get_settings)]) -> GitHubSync | None:
    """GitHub Actions, where it is set up (production); None elsewhere."""
    if settings.pipeline_dispatch_token is None or not settings.pipeline_repo:
        return None
    return GitHubSync(settings.pipeline_repo, settings.pipeline_dispatch_token)


def _github_id(request_id: int) -> str:
    return f"github-{request_id}"


@router.post("/sync/strava", response_model=SyncStatus, status_code=202)
def sync_strava(
    engine: Annotated[Engine, Depends(get_engine)],
    github: Annotated[GitHubSync | None, Depends(get_github_sync)],
    airflow: Annotated[AirflowClient | None, Depends(get_airflow)],
) -> SyncStatus:
    if github is None and airflow is None:
        raise ApiError(503, "sync_unavailable", "Sync now isn't set up here.")
    now = clock.now()
    with engine.begin() as conn:
        last = conn.execute(load_sql("api/sync_last_request.sql"), {"source": "strava"}).first()
        if last is not None and now - last.requested_at < COOLDOWN:
            wait = int((COOLDOWN - (now - last.requested_at)).total_seconds()) + 1
            raise ApiError(429, "sync_cooldown", f"Synced a moment ago. Try again in {wait} s.")
        running = conn.execute(load_sql("api/sync_run_in_progress.sql"), {"now": now}).scalar_one()
        if running:
            raise ApiError(409, "sync_running", "A Strava sync is already running.")

        if github is not None:
            # The workflow's "job" input: only the Strava sync, not the data checks.
            started = dispatch_workflow(
                github.repo,
                WORKFLOW,
                github.token,
                inputs={"job": "strava"},
                transport=github.transport,
            )
            if not started:
                raise ApiError(
                    502, "github_unavailable", "GitHub didn't start the sync. Try again soon."
                )
            airflow_run_id = None
        else:
            try:
                airflow_run_id = airflow.trigger(DAG_ID)
            except AirflowError as error:
                raise ApiError(502, "airflow_unavailable", str(error)) from None
        request_id = conn.execute(
            load_sql("api/sync_insert_request.sql"),
            {"source": "strava", "requested_at": now, "airflow_run_id": airflow_run_id},
        ).scalar_one()
    followed = airflow_run_id if airflow_run_id is not None else _github_id(request_id)
    return SyncStatus(requested_at=now, dag_run_id=followed, state="queued")


@router.get("/sync/strava", response_model=SyncStatus)
def sync_strava_status(
    engine: Annotated[Engine, Depends(get_engine)],
    airflow: Annotated[AirflowClient | None, Depends(get_airflow)],
) -> SyncStatus:
    with engine.connect() as conn:
        last = conn.execute(load_sql("api/sync_last_request.sql"), {"source": "strava"}).first()
        if last is None:
            return SyncStatus(requested_at=None, dag_run_id=None, state=None)
        if last.airflow_run_id is None:
            # Started on GitHub: the run row it writes says how it's going (none yet: queued).
            run = conn.execute(
                load_sql("api/sync_run_since.sql"), {"since": last.requested_at}
            ).first()
            state = RUN_STATES.get(run.status, "running") if run else "queued"
            return SyncStatus(
                requested_at=last.requested_at, dag_run_id=_github_id(last.id), state=state
            )
    if airflow is None:
        raise ApiError(503, "sync_unavailable", "Sync now isn't set up here.")
    try:
        state = airflow.run_state(DAG_ID, last.airflow_run_id)
    except AirflowError as error:
        raise ApiError(502, "airflow_unavailable", str(error)) from None
    return SyncStatus(requested_at=last.requested_at, dag_run_id=last.airflow_run_id, state=state)
