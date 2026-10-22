"""GET /api/v1/trends/training and /trends/nutrition: weekly or monthly trends.

Every number, including the change against the previous period (LAG) and the 7-day
rolling average, is computed by the mart functions in migration 0008. This module picks
how many periods to show and shapes the answer.
"""

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Engine

from app import clock
from app.auth import require_api_key
from app.db import get_engine, load_sql

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])

Grain = Literal["week", "month"]

# How many bars fit a phone-width card: 8 weeks is about two months, 6 months half a year.
PERIODS: dict[str, int] = {"week": 8, "month": 6}


class TrainingPeriod(BaseModel):
    start: date
    end: date
    current: bool  # the period still running: its numbers are "so far"
    sessions: int
    active_s: int
    run_m: float
    volume_kg: float
    prev_sessions: int | None
    prev_active_s: int | None
    active_change_pct: int | None  # None when the period before had no training


class TrainingTrend(BaseModel):
    grain: Grain
    periods: list[TrainingPeriod]


class NutritionPeriod(BaseModel):
    start: date
    end: date
    current: bool
    days_logged: int
    avg_kcal: int | None  # per logged day; None when nothing was logged
    avg_protein_g: int | None
    avg_budget: int | None
    days_within: int
    days_over: int
    status: str  # not_logged | not_set | within | over
    prev_avg_kcal: int | None


class Rolling(BaseModel):
    end_date: date  # yesterday: today is still being logged
    kcal_avg: int | None
    protein_avg_g: int | None
    days_logged: int


class NutritionTrend(BaseModel):
    grain: Grain
    rolling_7d: Rolling
    periods: list[NutritionPeriod]


def _int(value) -> int | None:
    """Rounded numeric from SQL as an int, so the JSON reads 1742, not 1742.0."""
    return None if value is None else int(value)


@router.get("/trends/training", response_model=TrainingTrend)
def training_trend(
    engine: Annotated[Engine, Depends(get_engine)], grain: Grain = "week"
) -> TrainingTrend:
    params = {"today": clock.today(), "grain": grain, "periods": PERIODS[grain]}
    with engine.connect() as conn:
        rows = conn.execute(load_sql("api/training_trend.sql"), params).all()
    return TrainingTrend(
        grain=grain,
        periods=[
            TrainingPeriod(
                start=row.period_start,
                end=row.period_end,
                current=row.is_current,
                sessions=row.sessions,
                active_s=row.active_s,
                run_m=float(row.run_m),
                volume_kg=float(row.volume_kg),
                prev_sessions=row.prev_sessions,
                prev_active_s=row.prev_active_s,
                active_change_pct=row.active_change_pct,
            )
            for row in rows
        ],
    )


@router.get("/trends/nutrition", response_model=NutritionTrend)
def nutrition_trend(
    engine: Annotated[Engine, Depends(get_engine)], grain: Grain = "week"
) -> NutritionTrend:
    today = clock.today()
    # The 7-day average ends yesterday: a half-logged today would pull it down.
    yesterday = today - timedelta(days=1)
    params = {"today": today, "grain": grain, "periods": PERIODS[grain]}
    with engine.connect() as conn:
        rows = conn.execute(load_sql("api/nutrition_trend.sql"), params).all()
        rolling = conn.execute(load_sql("api/nutrition_rolling.sql"), {"day": yesterday}).one()
    return NutritionTrend(
        grain=grain,
        rolling_7d=Rolling(
            end_date=yesterday,
            kcal_avg=_int(rolling.kcal_avg_7d),
            protein_avg_g=_int(rolling.protein_avg_7d),
            days_logged=rolling.days_logged_7d,
        ),
        periods=[
            NutritionPeriod(
                start=row.period_start,
                end=row.period_end,
                current=row.is_current,
                days_logged=row.days_logged,
                avg_kcal=_int(row.avg_kcal),
                avg_protein_g=_int(row.avg_protein_g),
                avg_budget=_int(row.avg_budget),
                days_within=row.days_within,
                days_over=row.days_over,
                status=row.status,
                prev_avg_kcal=_int(row.prev_avg_kcal),
            )
            for row in rows
        ],
    )
