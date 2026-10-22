"""The ten M2 data-quality checks: a pass test and a fail (or warn) test for each
(ARCHITECTURE.md 9). Checks guarding a database constraint break that constraint inside
a transaction that is rolled back, the same way as activity_unique in test_dq_checks.py.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from day_builder import add_activity, add_calories, add_target, date_key
from sqlalchemy import Connection, Engine, text

from include.db import load_sql
from include.dq.checks import run_check

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)  # 20:00 in Manila
TODAY = date(2026, 10, 21)


def result_of(engine: Engine, check: str) -> tuple[str, float | None]:
    result = run_check(engine, check, NOW)
    value = None if result.observed_value is None else float(result.observed_value)
    return result.status, value


def result_in(conn: Connection, check: str) -> tuple[str, float]:
    """Run a check on an open connection, to see rows of a transaction not yet committed."""
    row = conn.execute(load_sql(f"dq/{check}.sql"), {"now": NOW}).one()
    return row.status, float(row.observed_value)


def add_timed_activity(engine: Engine, strava_id: int, day: date, start: str, minutes: int):
    """An activity with a real time range, for the overlap check."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO raw.strava_activities (strava_id, payload, fetched_at) "
                "VALUES (:id, '{}', now())"
            ),
            {"id": strava_id},
        )
        conn.execute(
            text(
                "INSERT INTO core.dim_activity_type (strava_sport_type, app_type, label) "
                "VALUES ('Run', 'run', 'Run') ON CONFLICT DO NOTHING"
            )
        )
        conn.execute(
            text(
                "INSERT INTO core.fact_activity (strava_id, date_key, activity_type_key, "
                "started_at, started_local, ended_at, duration_s, source_fetched_at) "
                "SELECT :id, :date_key, activity_type_key, CAST(:started AS timestamptz), "
                "CAST(:local AS timestamp), "
                "CAST(:started AS timestamptz) + :seconds * interval '1 second', :seconds, now() "
                "FROM core.dim_activity_type WHERE strava_sport_type = 'Run'"
            ),
            {
                "id": strava_id,
                "date_key": date_key(day),
                "started": f"{day}T{start}:00+08:00",
                "local": f"{day} {start}",
                "seconds": minutes * 60,
            },
        )


def add_exercise(engine: Engine, name: str, muscle_group: str = "Chest") -> int:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO core.dim_exercise (exercise_name, equipment, muscle_group) "
                "VALUES (:name, NULL, :group) RETURNING exercise_key"
            ),
            {"name": name, "group": muscle_group},
        ).scalar_one()


def add_weight_set(engine: Engine, day: date, weight_kg: float, reps: int = 8) -> None:
    """One weight-and-reps set on the day's activity (add_activity first)."""
    exercise_key = add_exercise(engine, f"Bench Press {weight_kg}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO core.fact_set (activity_key, date_key, exercise_key, "
                "exercise_order, set_number, set_kind, weight_kg, reps, orig_weight, orig_unit) "
                "SELECT activity_key, date_key, :exercise_key, 1, 1, 'weight_reps', "
                ":kg, :reps, :kg, 'kg' FROM core.fact_activity WHERE strava_id = :id"
            ),
            {"exercise_key": exercise_key, "kg": weight_kg, "reps": reps, "id": date_key(day)},
        )


def set_duration(engine: Engine, day: date, seconds: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE core.fact_activity SET duration_s = :s WHERE strava_id = :id"),
            {"s": seconds, "id": date_key(day)},
        )


def add_quarantine(engine: Engine, count: int, resolved: bool = False) -> None:
    if count == 0:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ops.quarantine (source, entity_id, raw_content, reason_code, "
                "resolved_at) VALUES ('strava', '1', 'Set 1: ???', 'unparsed_line', "
                "CASE WHEN :resolved THEN now() END)"
            ),
            [{"resolved": resolved}] * count,
        )


# --- activity_not_null (guards NOT NULL) ---------------------------------------------------


def test_activity_not_null_passes_with_complete_activities(engine):
    add_activity(engine, TODAY)

    assert result_of(engine, "activity_not_null") == ("pass", 0)


def test_activity_not_null_fails_on_a_missing_duration(engine):
    add_activity(engine, TODAY)
    with engine.connect() as conn:
        transaction = conn.begin()
        conn.execute(text("ALTER TABLE core.fact_activity ALTER COLUMN duration_s DROP NOT NULL"))
        conn.execute(text("UPDATE core.fact_activity SET duration_s = NULL"))
        result = result_in(conn, "activity_not_null")
        transaction.rollback()

    assert result == ("fail", 1)


# --- activity_duration_range ---------------------------------------------------------------


def test_activity_duration_range_passes_for_a_normal_workout(engine):
    add_activity(engine, TODAY)  # 30 minutes

    assert result_of(engine, "activity_duration_range") == ("pass", 0)


@pytest.mark.parametrize("seconds", [0, 86401])
def test_activity_duration_range_warns_on_zero_or_over_a_day(engine, seconds):
    add_activity(engine, TODAY)
    set_duration(engine, TODAY, seconds)

    assert result_of(engine, "activity_duration_range") == ("warn", 1)


def test_activity_duration_range_allows_exactly_one_day(engine):
    add_activity(engine, TODAY)
    set_duration(engine, TODAY, 86400)

    assert result_of(engine, "activity_duration_range") == ("pass", 0)


# --- set_range -----------------------------------------------------------------------------


def test_set_range_passes_for_normal_sets(engine):
    add_activity(engine, TODAY)
    add_weight_set(engine, TODAY, 20)

    assert result_of(engine, "set_range") == ("pass", 0)


@pytest.mark.parametrize(("weight_kg", "reps"), [(600, 8), (20, 250)])
def test_set_range_warns_on_an_implausible_weight_or_reps(engine, weight_kg, reps):
    add_activity(engine, TODAY)
    add_weight_set(engine, TODAY, weight_kg, reps)

    assert result_of(engine, "set_range") == ("warn", 1)


def test_set_range_ignores_columns_a_set_kind_does_not_use(engine):
    # A bodyweight set: weight, distance and duration are NULL, not outliers.
    add_activity(engine, TODAY)
    exercise_key = add_exercise(engine, "Push Up")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO core.fact_set (activity_key, date_key, exercise_key, "
                "exercise_order, set_number, set_kind, reps) "
                "SELECT activity_key, date_key, :key, 1, 1, 'reps', 15 "
                "FROM core.fact_activity"
            ),
            {"key": exercise_key},
        )

    assert result_of(engine, "set_range") == ("pass", 0)


# --- calorie_daily_range -------------------------------------------------------------------


def test_calorie_daily_range_passes_for_a_normal_day(engine):
    add_calories(engine, TODAY, kcal=1800)

    assert result_of(engine, "calorie_daily_range") == ("pass", 0)


def test_calorie_daily_range_warns_when_a_day_adds_up_past_10000(engine):
    # Each sample is within its own CHECK (<= 5000); the day's total is not.
    for kcal in (4000, 4000, 2500):
        add_calories(engine, TODAY, kcal=kcal)
    add_calories(engine, TODAY - timedelta(days=1), kcal=1800)

    assert result_of(engine, "calorie_daily_range") == ("warn", 1)


# --- fk_integrity (guards the foreign keys) ------------------------------------------------


def test_fk_integrity_passes_when_every_fact_has_its_dimensions(engine):
    add_activity(engine, TODAY)
    add_weight_set(engine, TODAY, 20)
    add_calories(engine, TODAY)

    assert result_of(engine, "fk_integrity") == ("pass", 0)


def test_fk_integrity_fails_on_a_set_without_its_exercise(engine):
    add_activity(engine, TODAY)
    with engine.connect() as conn:
        transaction = conn.begin()
        conn.execute(text("ALTER TABLE core.fact_set DROP CONSTRAINT fact_set_exercise_key_fkey"))
        conn.execute(
            text(
                "INSERT INTO core.fact_set (activity_key, date_key, exercise_key, "
                "exercise_order, set_number, set_kind, reps) "
                "SELECT activity_key, date_key, 999999, 1, 1, 'reps', 10 "
                "FROM core.fact_activity"
            )
        )
        result = result_in(conn, "fk_integrity")
        transaction.rollback()

    assert result == ("fail", 1)


# --- quarantine_open -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("open_rows", "expected"),
    [(0, ("pass", 0)), (1, ("warn", 1)), (25, ("warn", 25)), (26, ("fail", 26))],
)
def test_quarantine_open_thresholds(engine, open_rows, expected):
    add_quarantine(engine, open_rows)

    assert result_of(engine, "quarantine_open") == expected


def test_quarantine_open_ignores_resolved_rows(engine):
    add_quarantine(engine, 30, resolved=True)

    assert result_of(engine, "quarantine_open") == ("pass", 0)


# --- unmapped_exercises --------------------------------------------------------------------


def test_unmapped_exercises_passes_when_every_exercise_has_a_group(engine):
    add_exercise(engine, "Incline Bench Press", "Chest")

    assert result_of(engine, "unmapped_exercises") == ("pass", 0)


def test_unmapped_exercises_warns_on_an_unmapped_exercise(engine):
    add_exercise(engine, "Incline Bench Press", "Chest")
    add_exercise(engine, "Cable Fly", "Unmapped")

    assert result_of(engine, "unmapped_exercises") == ("warn", 1)


# --- possible_duplicate_activity -----------------------------------------------------------


def test_possible_duplicate_passes_for_back_to_back_activities(engine):
    # A walk then a lift: touching end to start is not an overlap.
    add_timed_activity(engine, 1, TODAY, "07:00", 30)
    add_timed_activity(engine, 2, TODAY, "07:30", 60)

    assert result_of(engine, "possible_duplicate_activity") == ("pass", 0)


def test_possible_duplicate_warns_on_overlapping_activities(engine):
    add_timed_activity(engine, 1, TODAY, "17:00", 60)
    add_timed_activity(engine, 2, TODAY, "17:10", 55)
    add_timed_activity(engine, 3, TODAY - timedelta(days=1), "17:00", 60)

    assert result_of(engine, "possible_duplicate_activity") == ("warn", 1)


# --- target_present ------------------------------------------------------------------------


def test_target_present_passes_with_a_saved_target(engine):
    add_target(engine, TODAY, budget=1853)

    assert result_of(engine, "target_present") == ("pass", 1)


def test_target_present_warns_without_any_target(engine):
    assert result_of(engine, "target_present") == ("warn", 0)


# --- days_with_activity_no_calories (information only) -------------------------------------


def test_days_with_activity_no_calories_counts_the_last_14_days(engine):
    add_activity(engine, TODAY)  # no calories: counts
    add_activity(engine, TODAY - timedelta(days=13))  # no calories, first day in range
    add_activity(engine, TODAY - timedelta(days=2))  # has calories: does not count
    add_calories(engine, TODAY - timedelta(days=2))
    add_activity(engine, TODAY - timedelta(days=14))  # outside the 14 days

    assert result_of(engine, "days_with_activity_no_calories") == ("pass", 2)


def test_days_with_activity_no_calories_never_warns_or_fails(engine):
    for days_ago in range(14):
        add_activity(engine, TODAY - timedelta(days=days_ago))

    assert result_of(engine, "days_with_activity_no_calories") == ("pass", 14)
