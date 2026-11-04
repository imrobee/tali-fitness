"""GET /api/v1/activities (day-grouped list) and GET /api/v1/activities/{id} (detail).

Totals are computed in SQL (db/sql/api/), so the list and the detail always agree. This
module only groups the rows and shapes them for the page (UI_SPEC.md 6.1).
"""

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine

from app import clock
from app.auth import require_user
from app.db import get_engine, load_sql
from app.errors import ApiError

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])

DEFAULT_DAYS = 30  # "default last 30 days" (ARCHITECTURE.md 11)
MAX_DAYS = 366  # one year per request; older history comes from the calendar in Slice 7a


class ActivitySummary(BaseModel):
    id: int
    type: str
    title: str | None
    started_at: str
    duration_s: int
    moving_s: int | None  # run pace uses moving time (ARCHITECTURE.md 14 #3)
    distance_m: float | None
    parse_status: str | None
    exercise_count: int
    set_count: int
    volume_kg: float


class ActivityDay(BaseModel):
    date: date
    activities: list[ActivitySummary]


class ActivityList(BaseModel):
    from_date: date = Field(serialization_alias="from")
    to_date: date = Field(serialization_alias="to")
    days: list[ActivityDay]


class SetOut(BaseModel):
    number: int
    kind: str
    weight_kg: float | None
    orig_weight: float | None
    orig_unit: str | None
    reps: int | None
    distance_m: float | None
    duration_s: int | None


class ExerciseOut(BaseModel):
    order: int
    name: str
    equipment: str | None
    note: str | None
    sets: list[SetOut]


class ActivityDetail(BaseModel):
    id: int
    date: date
    type: str
    title: str | None
    started_at: str
    duration_s: int
    distance_m: float | None
    parse_status: str | None
    description_raw: str | None  # only when the sets are not the whole workout
    exercises: list[ExerciseOut]


def group_by_day(rows: Sequence) -> list[ActivityDay]:
    days: list[ActivityDay] = []
    for row in rows:
        summary = ActivitySummary(
            id=row.id,
            type=row.type,
            title=row.title,
            started_at=row.started_at.isoformat(),
            duration_s=row.duration_s,
            moving_s=row.moving_s,
            distance_m=_number(row.distance_m),
            parse_status=row.parse_status,
            exercise_count=row.exercise_count,
            set_count=row.set_count,
            volume_kg=_number(row.volume_kg),
        )
        if days and days[-1].date == row.day:
            days[-1].activities.append(summary)
        else:
            days.append(ActivityDay(date=row.day, activities=[summary]))
    return days


def group_exercises(rows: Sequence) -> list[ExerciseOut]:
    exercises: list[ExerciseOut] = []
    for row in rows:
        if not exercises or exercises[-1].order != row.exercise_order:
            exercises.append(
                ExerciseOut(
                    order=row.exercise_order,
                    name=row.exercise_name,
                    equipment=row.equipment,
                    note=row.exercise_note,
                    sets=[],
                )
            )
        exercises[-1].sets.append(
            SetOut(
                number=row.set_number,
                kind=row.set_kind,
                weight_kg=_number(row.weight_kg),
                orig_weight=_number(row.orig_weight),
                orig_unit=row.orig_unit,
                reps=row.reps,
                distance_m=_number(row.distance_m),
                duration_s=row.duration_s,
            )
        )
    return exercises


def _number(value):
    """Decimal (from numeric columns) as float, so the JSON reads as a number."""
    return None if value is None else float(value)


@router.get("/activities", response_model=ActivityList)
def list_activities(
    engine: Annotated[Engine, Depends(get_engine)],
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
) -> ActivityList:
    today = clock.today()
    end = end or today
    start = start or end - timedelta(days=DEFAULT_DAYS - 1)
    if start > end:
        raise ApiError(422, "invalid_payload", "from must be on or before to.")
    if (end - start).days >= MAX_DAYS:
        raise ApiError(422, "date_out_of_range", f"The range can be at most {MAX_DAYS} days.")
    with engine.connect() as conn:
        rows = conn.execute(
            load_sql("api/activities_in_range.sql"), {"start": start, "end": end}
        ).all()
    return ActivityList(from_date=start, to_date=end, days=group_by_day(rows))


@router.get("/activities/{activity_id}", response_model=ActivityDetail)
def get_activity(
    activity_id: int, engine: Annotated[Engine, Depends(get_engine)]
) -> ActivityDetail:
    with engine.connect() as conn:
        return read_activity(conn, activity_id)


def read_activity(conn: Connection, activity_id: int) -> ActivityDetail:
    header = conn.execute(load_sql("api/activity_detail.sql"), {"id": activity_id}).one_or_none()
    if header is None:
        raise ApiError(404, "not_found", "No activity with that id.")
    sets = conn.execute(load_sql("api/activity_sets.sql"), {"id": activity_id}).all()
    return ActivityDetail(
        id=header.id,
        date=header.day,
        type=header.type,
        title=header.title,
        started_at=header.started_at.isoformat(),
        duration_s=header.duration_s,
        distance_m=_number(header.distance_m),
        parse_status=header.parse_status,
        description_raw=header.description_raw,
        exercises=group_exercises(sets),
    )
