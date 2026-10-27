"""GET /api/v1/weight?from=&to=: the weight trend against the goal (ARCHITECTURE.md 5.5).

The averages, the change and the goal in effect each day are computed by
mart.fn_weight_trend. This module picks the latest weigh-in and the distance to goal.
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine

from app import clock
from app.auth import require_api_key
from app.db import get_engine, load_sql
from app.errors import ApiError

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])

DEFAULT_DAYS = 90
MAX_DAYS = 366


class WeightDay(BaseModel):
    date: date
    weight_kg: float | None
    avg_7d_kg: float | None
    change_7d_kg: float | None
    goal_kg: float | None
    status: str  # not_logged | not_set | at_or_below | above


class Weight(BaseModel):
    from_date: date = Field(serialization_alias="from")
    to_date: date = Field(serialization_alias="to")
    latest_date: date | None  # the last day in the range with a weigh-in
    latest_kg: float | None
    avg_7d_kg: float | None  # the 7-day average on that day
    change_7d_kg: float | None
    goal_kg: float | None  # the goal in effect on the last day of the range
    to_goal_kg: float | None  # the 7-day average minus the goal; positive is above it
    days: list[WeightDay]


def read_weight(conn: Connection, start: date, end: date) -> Weight:
    rows = conn.execute(load_sql("api/weight_trend.sql"), {"start": start, "end": end}).all()
    days = [
        WeightDay(
            date=row.day,
            weight_kg=_float(row.weight_kg),
            avg_7d_kg=_float(row.avg_7d_kg),
            change_7d_kg=_float(row.change_7d_kg),
            goal_kg=_float(row.goal_kg),
            status=row.status,
        )
        for row in rows
    ]
    logged = [day for day in days if day.weight_kg is not None]
    latest = logged[-1] if logged else None
    goal = days[-1].goal_kg if days else None
    return Weight(
        from_date=start,
        to_date=end,
        latest_date=latest.date if latest else None,
        latest_kg=latest.weight_kg if latest else None,
        avg_7d_kg=latest.avg_7d_kg if latest else None,
        change_7d_kg=latest.change_7d_kg if latest else None,
        goal_kg=goal,
        to_goal_kg=None if latest is None or goal is None else round(latest.avg_7d_kg - goal, 2),
        days=days,
    )


def _float(value) -> float | None:
    return None if value is None else float(value)


@router.get("/weight", response_model=Weight)
def weight(
    engine: Annotated[Engine, Depends(get_engine)],
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
) -> Weight:
    today = clock.today()
    end = end or today
    start = start or end - timedelta(days=DEFAULT_DAYS - 1)
    if start > end:
        raise ApiError(422, "invalid_payload", "from must be on or before to.")
    if (end - start).days >= MAX_DAYS:
        raise ApiError(422, "date_out_of_range", f"The range can be at most {MAX_DAYS} days.")
    with engine.connect() as conn:
        return read_weight(conn, start, end)
