"""GET/PUT /api/v1/me: nickname, time zone, and calorie/protein targets.

Targets are history, not a setting: saving inserts a row effective today, so past days
keep the targets they had (ARCHITECTURE.md 5.3).
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine

from app import clock
from app.auth import require_api_key
from app.db import get_engine, load_sql

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


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


class Me(BaseModel):
    nickname: str | None
    timezone: str
    targets: TargetsOut | None  # the targets in effect today
    weight_goal_kg: float | None  # the weight goal in effect today, always in kg
    weight_unit: Literal["kg", "lb"]  # how the app shows and asks for weights
    earliest_date: date


def read_me(conn: Connection) -> Me:
    today = clock.today()
    profile = conn.execute(load_sql("api/profile.sql")).one()
    target = conn.execute(load_sql("api/target_in_effect.sql"), {"day": today}).one_or_none()
    weight_goal = conn.execute(
        load_sql("api/weight_goal_in_effect.sql"), {"day": today}
    ).scalar_one_or_none()
    first_day = conn.execute(load_sql("api/day_status.sql"), {"today": today}).first()
    return Me(
        nickname=profile.nickname,
        timezone=profile.timezone,
        targets=TargetsOut(**target._mapping) if target else None,
        weight_goal_kg=None if weight_goal is None else float(weight_goal),
        weight_unit=profile.weight_unit,
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
        return read_me(conn)
