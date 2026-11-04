"""GET /api/v1/calendar: the week or month calendar on the Activities page.

The server decides the grid (full Monday-Sunday weeks), which days are in the future, and
where the previous and next buttons go, so the page only draws what it gets
(ARCHITECTURE.md 4: the browser never decides time). Named activity_calendar so it never
shadows Python's own `calendar` module.
"""

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Connection, Engine

from app import clock
from app.auth import require_user
from app.db import get_engine, load_sql
from app.errors import ApiError

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])

View = Literal["week", "month"]


class CalendarDay(BaseModel):
    date: date
    in_period: bool  # False for the grey days of the neighbouring months
    future: bool
    activity_count: int
    primary_activity_type: str | None  # the longest activity's type: the circle's icon
    recovery: bool


class Calendar(BaseModel):
    view: View
    today: date
    period_start: date
    period_end: date
    previous: date | None  # the date to ask for next; None at the first data period
    next: date | None  # None once the period contains today
    days: list[CalendarDay]


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def period_of(view: View, day: date) -> tuple[date, date]:
    """The week (Monday to Sunday) or the calendar month that contains `day`."""
    if view == "week":
        start = monday_of(day)
        return start, start + timedelta(days=6)
    start = day.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    return start, next_month - timedelta(days=1)


def grid_of(start: date, end: date) -> list[date]:
    """Every day of the full weeks that cover start..end."""
    first = monday_of(start)
    last = monday_of(end) + timedelta(days=6)
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def read_calendar(conn: Connection, view: View, day: date, today: date) -> Calendar:
    status = conn.execute(load_sql("api/day_status.sql"), {"today": today}).all()
    earliest = status[0].day if status else today
    first_period_start, _ = period_of(view, earliest)
    if day > today or day < first_period_start:
        raise ApiError(
            422, "date_out_of_range", f"date must be between {first_period_start} and {today}."
        )

    start, end = period_of(view, day)
    grid = grid_of(start, end)
    params = {"start": grid[0], "end": grid[-1]}
    counts = {
        row.day: row.activity_count
        for row in conn.execute(load_sql("api/calendar_counts.sql"), params)
    }
    types = {
        row.day: row.app_type
        for row in conn.execute(load_sql("api/primary_activity_types.sql"), params)
    }
    # A rest day (ARCHITECTURE.md 8): the calendar shows the snowflake when it had no workout.
    recovery_days = {row.day for row in status if row.kind == "recovery"}

    days = [
        CalendarDay(
            date=d,
            in_period=start <= d <= end,
            future=d > today,
            activity_count=counts.get(d, 0),
            primary_activity_type=types.get(d),
            recovery=d in recovery_days,
        )
        for d in grid
    ]
    previous_start, _ = period_of(view, start - timedelta(days=1))
    return Calendar(
        view=view,
        today=today,
        period_start=start,
        period_end=end,
        previous=previous_start if previous_start >= first_period_start else None,
        next=end + timedelta(days=1) if end < today else None,
        days=days,
    )


@router.get("/calendar", response_model=Calendar)
def calendar(
    engine: Annotated[Engine, Depends(get_engine)],
    view: View = "month",
    day: Annotated[date | None, Query(alias="date")] = None,
) -> Calendar:
    today = clock.today()
    with engine.connect() as conn:
        return read_calendar(conn, view, day or today, today)
