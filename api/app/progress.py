"""Progress views (PROJECT_PLAN Slice 7b): personal records, weekly volume per muscle group,
and last week against the week before. Every number comes from the mart functions in
migration 0012; this module shapes them for the pages.
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Engine

from app import clock
from app.auth import require_api_key
from app.db import get_engine, load_sql

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])

# A record set in the last 14 days is marked "New" on the page.
RECENT_DAYS = 14

# The muscle group of an exercise not yet in db/seeds/exercise_muscle_map.csv. The
# unmapped_exercises data-quality check reports those; the pages never show the word.
UNMAPPED = "Unmapped"


def _muscle(group: str) -> str | None:
    return None if group == UNMAPPED else group


def _float(value) -> float | None:
    return None if value is None else float(value)


class PersonalRecord(BaseModel):
    exercise: str
    equipment: str | None
    muscle_group: str | None  # None until the exercise is mapped to a muscle group
    e1rm_kg: float  # estimated one-rep max (Epley)
    weight_kg: float
    reps: int
    date: date
    activity_id: int
    prev_e1rm_kg: float | None  # the best before this record; None if it was the first
    sessions: int
    recent: bool


class PersonalRecords(BaseModel):
    records: list[PersonalRecord]


class MuscleWeek(BaseModel):
    muscle_group: str
    sets: int
    volume_kg: float
    prev_sets: int
    prev_volume_kg: float


class MuscleVolume(BaseModel):
    week_start: date
    week_end: date
    groups: list[MuscleWeek]


class WeeklySummary(BaseModel):
    week_start: date
    week_end: date
    qualifying_days: int
    prev_qualifying_days: int | None
    sessions: int
    prev_sessions: int | None
    active_s: int
    prev_active_s: int | None
    run_m: float
    volume_kg: float
    days_logged: int
    avg_kcal: float | None
    prev_avg_kcal: float | None
    avg_protein_g: float | None
    avg_weight_kg: float | None
    prev_avg_weight_kg: float | None


@router.get("/records", response_model=PersonalRecords)
def personal_records(engine: Annotated[Engine, Depends(get_engine)]) -> PersonalRecords:
    today = clock.today()
    with engine.connect() as conn:
        rows = conn.execute(load_sql("api/personal_records.sql"), {"today": today}).all()
    return PersonalRecords(
        records=[
            PersonalRecord(
                exercise=row.exercise_name,
                equipment=row.equipment,
                muscle_group=_muscle(row.muscle_group),
                e1rm_kg=float(row.best_e1rm_kg),
                weight_kg=float(row.weight_kg),
                reps=row.reps,
                date=row.day,
                activity_id=row.activity_key,
                prev_e1rm_kg=_float(row.prev_e1rm_kg),
                sessions=row.sessions,
                recent=row.day > today - timedelta(days=RECENT_DAYS),
            )
            for row in rows
        ]
    )


@router.get("/muscle-volume", response_model=MuscleVolume)
def muscle_volume(engine: Annotated[Engine, Depends(get_engine)]) -> MuscleVolume:
    # The last finished week, like the trend headlines (DECISIONS D82): its Sunday is the
    # day before this week's Monday.
    today = clock.today()
    last_sunday = today - timedelta(days=today.weekday() + 1)
    with engine.connect() as conn:
        rows = conn.execute(load_sql("api/muscle_volume.sql"), {"today": last_sunday}).all()
    week_start = last_sunday - timedelta(days=6)
    return MuscleVolume(
        week_start=week_start,
        week_end=last_sunday,
        groups=[
            MuscleWeek(
                muscle_group=row.muscle_group,
                sets=row.sets,
                volume_kg=float(row.volume_kg),
                prev_sets=row.prev_sets or 0,
                prev_volume_kg=float(row.prev_volume_kg or 0),
            )
            for row in rows
            if (row.sets > 0 or (row.prev_sets or 0) > 0) and row.muscle_group != UNMAPPED
        ],
    )


@router.get("/summary/week", response_model=WeeklySummary)
def weekly_summary(engine: Annotated[Engine, Depends(get_engine)]) -> WeeklySummary:
    with engine.connect() as conn:
        row = conn.execute(load_sql("api/weekly_summary.sql"), {"today": clock.today()}).one()
    return WeeklySummary(
        week_start=row.week_start,
        week_end=row.week_end,
        qualifying_days=row.qualifying_days,
        prev_qualifying_days=row.prev_qualifying_days,
        sessions=row.sessions,
        prev_sessions=row.prev_sessions,
        active_s=row.active_s,
        prev_active_s=row.prev_active_s,
        run_m=float(row.run_m),
        volume_kg=float(row.volume_kg),
        days_logged=row.days_logged,
        avg_kcal=_float(row.avg_kcal),
        prev_avg_kcal=_float(row.prev_avg_kcal),
        avg_protein_g=_float(row.avg_protein_g),
        avg_weight_kg=_float(row.avg_weight_kg),
        prev_avg_weight_kg=_float(row.prev_avg_weight_kg),
    )
