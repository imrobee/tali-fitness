"""POST /api/v1/sync/strava ("Sync now") and GET /api/v1/sync/strava (its progress).

The API asks Airflow to run strava_sync now (DECISIONS D78). Guards: one request per
2 minutes, and none while a Strava run is in progress; the DAG's max_active_runs=1 is the
last line of defence against two runs at once.
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Engine

from app import clock
from app.airflow import AirflowClient, AirflowError, get_airflow
from app.auth import require_api_key
from app.db import get_engine, load_sql
from app.errors import ApiError

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])

DAG_ID = "strava_sync"
COOLDOWN = timedelta(minutes=2)


class SyncStatus(BaseModel):
    requested_at: datetime | None
    dag_run_id: str | None
    state: str | None  # queued | running | success | failed; None before any request


def _require(airflow: AirflowClient | None) -> AirflowClient:
    if airflow is None:
        raise ApiError(
            503, "sync_unavailable", "Sync now needs Airflow, which is not running here."
        )
    return airflow


@router.post("/sync/strava", response_model=SyncStatus, status_code=202)
def sync_strava(
    engine: Annotated[Engine, Depends(get_engine)],
    airflow: Annotated[AirflowClient | None, Depends(get_airflow)],
) -> SyncStatus:
    client = _require(airflow)
    now = clock.now()
    with engine.begin() as conn:
        last = conn.execute(load_sql("api/sync_last_request.sql"), {"source": "strava"}).first()
        if last is not None and now - last.requested_at < COOLDOWN:
            wait = int((COOLDOWN - (now - last.requested_at)).total_seconds()) + 1
            raise ApiError(429, "sync_cooldown", f"Synced a moment ago. Try again in {wait} s.")
        running = conn.execute(load_sql("api/sync_run_in_progress.sql"), {"now": now}).scalar_one()
        if running:
            raise ApiError(409, "sync_running", "A Strava sync is already running.")
        try:
            run_id = client.trigger(DAG_ID)
        except AirflowError as error:
            raise ApiError(502, "airflow_unavailable", str(error)) from None
        conn.execute(
            load_sql("api/sync_insert_request.sql"),
            {"source": "strava", "requested_at": now, "airflow_run_id": run_id},
        )
    return SyncStatus(requested_at=now, dag_run_id=run_id, state="queued")


@router.get("/sync/strava", response_model=SyncStatus)
def sync_strava_status(
    engine: Annotated[Engine, Depends(get_engine)],
    airflow: Annotated[AirflowClient | None, Depends(get_airflow)],
) -> SyncStatus:
    with engine.connect() as conn:
        last = conn.execute(load_sql("api/sync_last_request.sql"), {"source": "strava"}).first()
    if last is None:
        return SyncStatus(requested_at=None, dag_run_id=None, state=None)
    try:
        state = _require(airflow).run_state(DAG_ID, last.airflow_run_id)
    except AirflowError as error:
        raise ApiError(502, "airflow_unavailable", str(error)) from None
    return SyncStatus(requested_at=last.requested_at, dag_run_id=last.airflow_run_id, state=state)
