"""GET /api/v1/pipeline/health: the Me page's "Data and sync" panel (ARCHITECTURE.md 10).

The status of each source and the open quarantine count are decided in SQL, next to the
freshness thresholds. This module only shapes the answer for the page.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Connection, Engine

from app import clock
from app.auth import require_api_key
from app.db import get_engine, load_sql

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


class SourceHealth(BaseModel):
    source: str  # strava | health
    last_success_at: datetime | None
    status: str  # ok | delayed | failed
    failures_7d: int


class QuarantineItem(BaseModel):
    source: str
    entity_id: str
    line_no: int | None
    reason_code: str
    raw_snippet: str
    first_seen_at: datetime


class Quarantine(BaseModel):
    open: int
    by_reason: dict[str, int]
    recent: list[QuarantineItem]


class DqCheck(BaseModel):
    check_name: str
    status: str  # pass | warn | fail
    observed_value: float | None
    threshold: str
    checked_at: datetime


class DataQuality(BaseModel):
    passed: int
    warnings: int
    failed: int
    checked_at: datetime | None
    checks: list[DqCheck]


class PipelineHealth(BaseModel):
    # The server's clock: the page measures "9 hours ago" from it, never from the phone's
    # clock, so the words always agree with the status (ARCHITECTURE.md 4).
    now: datetime
    sources: list[SourceHealth]
    quarantine: Quarantine
    dq: DataQuality


def read_pipeline_health(conn: Connection, now: datetime) -> PipelineHealth:
    sources = [
        SourceHealth(**row._mapping)
        for row in conn.execute(load_sql("api/pipeline_sources.sql"), {"now": now})
    ]

    counts = conn.execute(load_sql("api/pipeline_quarantine_counts.sql")).all()
    recent = conn.execute(load_sql("api/pipeline_quarantine_recent.sql")).all()
    quarantine = Quarantine(
        open=sum(row.open_count for row in counts),
        by_reason={row.reason_code: row.open_count for row in counts},
        recent=[QuarantineItem(**row._mapping) for row in recent],
    )

    checks = [
        DqCheck(
            check_name=row.check_name,
            status=row.status,
            observed_value=None if row.observed_value is None else float(row.observed_value),
            threshold=row.threshold,
            checked_at=row.checked_at,
        )
        for row in conn.execute(load_sql("api/pipeline_dq_latest.sql"))
    ]
    statuses = [check.status for check in checks]
    dq = DataQuality(
        passed=statuses.count("pass"),
        warnings=statuses.count("warn"),
        failed=statuses.count("fail"),
        checked_at=checks[0].checked_at if checks else None,
        checks=checks,
    )
    return PipelineHealth(now=now, sources=sources, quarantine=quarantine, dq=dq)


@router.get("/pipeline/health", response_model=PipelineHealth)
def pipeline_health(engine: Annotated[Engine, Depends(get_engine)]) -> PipelineHealth:
    with engine.connect() as conn:
        return read_pipeline_health(conn, clock.now())
