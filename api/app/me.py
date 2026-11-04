"""GET/PUT /api/v1/me: nickname, time zone, targets, weight, and the streak settings
(relaxed weekends; PUT/DELETE /api/v1/vacation for a vacation or injury break).

Targets are history, not a setting: saving inserts a row effective today, so past days
keep the targets they had (ARCHITECTURE.md 5.3).
"""

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine

from app import clock
from app.auth import require_user
from app.db import get_engine, load_sql
from app.errors import ApiError

VACATION_MAX_DAYS = 90  # the CHECK in migration 0014
VACATION_AHEAD_DAYS = 365

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])


class Targets(BaseModel):
    # Sanity limits from UI_SPEC.md 6.3.
    calorie_budget: int = Field(ge=800, le=6000)
    protein_goal: int = Field(ge=0, le=400)


class TargetsOut(Targets):
    effective_from: date


class MeUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=40)
    targets: Targets | None = None
    weight_goal_kg: float | None = Field(default=None, ge=30, le=250)
    weight_unit: Literal["kg", "lb"] | None = None
    lenient_weekends: bool | None = None  # applies from today (DECISIONS D97)


class Period(BaseModel):
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class Me(BaseModel):
    nickname: str | None
    timezone: str
    targets: TargetsOut | None  # the targets in effect today
    weight_goal_kg: float | None  # the weight goal in effect today, always in kg
    weight_unit: Literal["kg", "lb"]  # how the app shows and asks for weights
    lenient_weekends: bool  # in effect today: only a missed day breaks on weekends
    vacation: Period | None  # the period still running or still to come
    last_vacation: Period | None  # the most recent one that has ended
    earliest_date: date


def read_me(conn: Connection) -> Me:
    today = clock.today()
    profile = conn.execute(load_sql("api/profile.sql")).one()
    target = conn.execute(load_sql("api/target_in_effect.sql"), {"day": today}).one_or_none()
    weight_goal = conn.execute(
        load_sql("api/weight_goal_in_effect.sql"), {"day": today}
    ).scalar_one_or_none()
    first_day = conn.execute(load_sql("api/day_status.sql"), {"today": today}).first()
    lenient = conn.execute(
        load_sql("api/streak_setting_in_effect.sql"), {"day": today}
    ).scalar_one()
    current = conn.execute(load_sql("api/vacation_current.sql"), {"today": today}).first()
    last = conn.execute(load_sql("api/vacation_last_ended.sql"), {"today": today}).first()
    return Me(
        nickname=profile.nickname,
        timezone=profile.timezone,
        targets=TargetsOut(**target._mapping) if target else None,
        weight_goal_kg=None if weight_goal is None else float(weight_goal),
        weight_unit=profile.weight_unit,
        lenient_weekends=lenient,
        vacation=Period(from_date=current.start_date, to_date=current.end_date)
        if current
        else None,
        last_vacation=Period(from_date=last.start_date, to_date=last.end_date) if last else None,
        earliest_date=first_day.day if first_day else today,
    )


@router.get("/me", response_model=Me)
def get_me(engine: Annotated[Engine, Depends(get_engine)]) -> Me:
    with engine.connect() as conn:
        return read_me(conn)


@router.put("/me", response_model=Me)
def put_me(update: MeUpdate, engine: Annotated[Engine, Depends(get_engine)]) -> Me:
    with engine.begin() as conn:
        # Only fields present in the request change; {"nickname": null} clears it.
        if "nickname" in update.model_fields_set:
            nickname = update.nickname.strip() if update.nickname else None
            conn.execute(load_sql("api/update_nickname.sql"), {"nickname": nickname or None})
        if update.targets is not None:
            conn.execute(
                load_sql("api/save_target.sql"),
                {"today": clock.today(), **update.targets.model_dump()},
            )
        if update.weight_unit is not None:
            conn.execute(
                load_sql("api/update_weight_unit.sql"), {"weight_unit": update.weight_unit}
            )
        if update.weight_goal_kg is not None:
            conn.execute(
                load_sql("api/save_weight_goal.sql"),
                {"today": clock.today(), "goal_kg": update.weight_goal_kg},
            )
        if update.lenient_weekends is not None:
            conn.execute(
                load_sql("api/save_streak_setting.sql"),
                {"today": clock.today(), "lenient_weekends": update.lenient_weekends},
            )
        return read_me(conn)


@router.put("/vacation", response_model=Me)
def put_vacation(period: Period, engine: Annotated[Engine, Depends(get_engine)]) -> Me:
    """Set the vacation or injury period. It replaces the one still running or to come;
    with none, it adds a new one, which may cover past days (a forgotten vacation)."""
    today = clock.today()
    start, end = period.from_date, period.to_date
    if start > end:
        raise ApiError(422, "invalid_payload", "From must be on or before To.")
    if (end - start).days >= VACATION_MAX_DAYS:
        raise ApiError(422, "invalid_payload", f"A break can be at most {VACATION_MAX_DAYS} days.")
    if end > today + timedelta(days=VACATION_AHEAD_DAYS):
        raise ApiError(422, "date_out_of_range", "A break can be set up to a year ahead.")
    with engine.begin() as conn:
        current = conn.execute(load_sql("api/vacation_current.sql"), {"today": today}).first()
        params = {"id": current.id if current else None, "start": start, "end": end}
        if conn.execute(load_sql("api/vacation_overlaps.sql"), params).scalar_one():
            raise ApiError(422, "vacation_overlap", "These dates overlap an earlier break.")
        if current:
            conn.execute(load_sql("api/vacation_update.sql"), params)
        else:
            conn.execute(load_sql("api/vacation_insert.sql"), params)
        return read_me(conn)


@router.delete("/vacation", status_code=204)
def delete_vacation(engine: Annotated[Engine, Depends(get_engine)]) -> Response:
    """End the vacation still running or to come. Past ones stay: they protected those days."""
    with engine.begin() as conn:
        current = conn.execute(
            load_sql("api/vacation_current.sql"), {"today": clock.today()}
        ).first()
        if current:
            conn.execute(load_sql("api/vacation_delete.sql"), {"id": current.id})
    return Response(status_code=204)
