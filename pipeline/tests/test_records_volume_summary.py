"""Personal records, weekly muscle volume and the weekly summary (migration 0012).

Today is Wednesday 2026-10-21 (day_builder.TODAY): last week is Oct 12-18, the week
before is Oct 5-11.
"""

from datetime import date

from day_builder import TODAY, add_calories, add_recovery
from sqlalchemy import Engine, text
from test_trends import add_session


def add_set(
    engine: Engine,
    strava_id: int,
    exercise: str,
    number: int,
    weight_kg: float | None,
    reps: int,
    muscle: str = "Chest",
    order: int = 1,
) -> None:
    kind = "weight_reps" if weight_kg is not None else "reps"
    with engine.begin() as conn:
        exercise_key = conn.execute(
            text(
                "INSERT INTO core.dim_exercise (exercise_name, equipment, muscle_group) "
                "VALUES (:name, NULL, :muscle) ON CONFLICT (exercise_name, equipment) "
                "DO UPDATE SET muscle_group = EXCLUDED.muscle_group RETURNING exercise_key"
            ),
            {"name": exercise, "muscle": muscle},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO core.fact_set (activity_key, date_key, exercise_key, "
                "exercise_order, set_number, set_kind, weight_kg, reps, orig_weight, orig_unit) "
                "SELECT activity_key, date_key, :exercise_key, :order, :number, :kind, "
                "CAST(:weight AS numeric), :reps, CAST(:weight AS numeric), "
                "CASE WHEN :kind = 'weight_reps' THEN 'kg' END "
                "FROM core.fact_activity WHERE strava_id = :id"
            ),
            {
                "exercise_key": exercise_key,
                "order": order,
                "number": number,
                "kind": kind,
                "weight": weight_kg,
                "reps": reps,
                "id": strava_id,
            },
        )


def lift(engine: Engine, day: date, strava_id: int) -> int:
    add_session(engine, day, strava_id, minutes=60, sport="WeightTraining", app_type="strength")
    return strava_id


def rows(engine: Engine, sql: str, **params) -> list:
    with engine.connect() as conn:
        return conn.execute(text(sql), params).all()


def records(engine: Engine, today: date = TODAY) -> dict:
    found = rows(engine, "SELECT * FROM mart.fn_personal_records(:today)", today=today)
    return {row.exercise_name: row for row in found}


# --- personal records ----------------------------------------------------------------------


def test_the_record_is_the_best_estimate_not_the_heaviest_weight(engine):
    session = lift(engine, date(2026, 10, 13), 1)
    add_set(engine, session, "Bench Press", 1, 100, 1)  # 100 x (1 + 1/30) = 103.33
    add_set(engine, session, "Bench Press", 2, 90, 5)  # 90 x (1 + 5/30) = 105

    best = records(engine)["Bench Press"]

    assert (float(best.weight_kg), best.reps, float(best.best_e1rm_kg)) == (90, 5, 105)


def test_sets_above_12_reps_are_left_out(engine):
    session = lift(engine, date(2026, 10, 13), 1)
    add_set(engine, session, "Bench Press", 1, 60, 20)  # 100 by Epley, but not trusted
    add_set(engine, session, "Bench Press", 2, 70, 8)

    assert float(records(engine)["Bench Press"].weight_kg) == 70


def test_the_previous_best_is_the_best_before_the_record(engine):
    add_set(engine, lift(engine, date(2026, 10, 6), 1), "Squat", 1, 80, 5)  # 93.33
    add_set(engine, lift(engine, date(2026, 10, 13), 2), "Squat", 1, 90, 5)  # 105

    best = records(engine)["Squat"]

    assert (best.day, float(best.prev_e1rm_kg), best.sessions) == (date(2026, 10, 13), 93.33, 2)


def test_a_tie_keeps_the_first_time_it_was_lifted(engine):
    add_set(engine, lift(engine, date(2026, 10, 6), 1), "Squat", 1, 90, 5)
    add_set(engine, lift(engine, date(2026, 10, 13), 2), "Squat", 1, 90, 5)

    best = records(engine)["Squat"]

    assert (best.day, best.prev_e1rm_kg) == (date(2026, 10, 6), None)


def test_bodyweight_sets_and_sets_after_today_are_left_out(engine):
    add_set(engine, lift(engine, date(2026, 10, 13), 1), "Push Up", 1, None, 20)
    add_set(engine, lift(engine, date(2026, 10, 22), 2), "Bench Press", 1, 100, 5)

    assert records(engine) == {}


# --- muscle volume -------------------------------------------------------------------------


def volume(engine: Engine, weeks: int = 2) -> list:
    return rows(
        engine, "SELECT * FROM mart.fn_muscle_volume(:today, :weeks)", today=TODAY, weeks=weeks
    )


def test_sets_and_volume_per_muscle_group_per_week(engine):
    session = lift(engine, date(2026, 10, 13), 1)
    add_set(engine, session, "Bench Press", 1, 50, 10, muscle="Chest")
    add_set(engine, session, "Bench Press", 2, 50, 8, muscle="Chest")
    add_set(engine, session, "Pull Up", 1, None, 10, muscle="Back", order=2)

    last_week = {r.muscle_group: r for r in volume(engine) if r.week_start == date(2026, 10, 12)}

    assert (last_week["Chest"].sets, float(last_week["Chest"].volume_kg)) == (2, 900)
    assert (last_week["Back"].sets, float(last_week["Back"].volume_kg)) == (1, 0)  # bodyweight


def test_a_muscle_not_trained_this_week_still_has_a_row_of_zeros(engine):
    add_set(engine, lift(engine, date(2026, 10, 13), 1), "Bench Press", 1, 50, 10)

    this_week = [r for r in volume(engine) if r.week_start == date(2026, 10, 19)]

    assert [(r.muscle_group, r.sets, r.prev_sets) for r in this_week] == [("Chest", 0, 1)]


def test_the_oldest_week_shown_compares_with_the_hidden_week(engine):
    add_set(engine, lift(engine, date(2026, 10, 6), 1), "Bench Press", 1, 50, 10)  # hidden week
    add_set(engine, lift(engine, date(2026, 10, 13), 2), "Bench Press", 1, 50, 10)
    add_set(engine, lift(engine, date(2026, 10, 13), 3), "Bench Press", 2, 50, 10)

    oldest = volume(engine)[0]

    assert (oldest.week_start, oldest.sets, oldest.prev_sets) == (date(2026, 10, 12), 2, 1)


# --- weekly summary ------------------------------------------------------------------------


def add_weight(engine: Engine, day: date, kg: float) -> None:
    with engine.begin() as conn:
        batch_id = conn.execute(
            text(
                "INSERT INTO raw.health_batches (window_start, window_end, device_tz, "
                "payload_sha256, payload) VALUES (:d, :d, 'Asia/Manila', gen_random_uuid()::text, "
                "'{}') RETURNING batch_id"
            ),
            {"d": day},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO core.fact_body_mass (local_date, date_key, weight_kg, start_ts, "
                "batch_id) VALUES (:d, :key, :kg, now(), :b)"
            ),
            {
                "d": day,
                "key": day.year * 10000 + day.month * 100 + day.day,
                "kg": kg,
                "b": batch_id,
            },
        )


def summary(engine: Engine):
    (row,) = rows(engine, "SELECT * FROM mart.fn_weekly_summary(:today)", today=TODAY)
    return row


def test_the_summary_is_last_week_against_the_week_before(engine):
    for day, strava_id in [
        (date(2026, 10, 6), 1),
        (date(2026, 10, 13), 2),
        (date(2026, 10, 15), 3),
    ]:
        add_session(engine, day, strava_id, minutes=30)
        add_calories(engine, day, kcal=1800)
    add_session(engine, date(2026, 10, 20), 4, minutes=30)  # this week: not in the summary

    row = summary(engine)

    assert (row.week_start, row.week_end) == (date(2026, 10, 12), date(2026, 10, 18))
    assert (row.sessions, row.prev_sessions, row.active_s) == (2, 1, 3600)
    assert (row.qualifying_days, row.prev_qualifying_days) == (2, 1)
    assert (row.days_logged, row.avg_kcal) == (2, 1800)


def test_the_summary_counts_the_whole_of_last_week_on_a_monday(engine):
    add_session(engine, date(2026, 10, 18), 1, minutes=30)  # last Sunday

    (row,) = rows(engine, "SELECT * FROM mart.fn_weekly_summary(:today)", today=date(2026, 10, 19))

    assert (row.week_start, row.sessions) == (date(2026, 10, 12), 1)


def test_the_summary_compares_the_average_weight(engine):
    add_weight(engine, date(2026, 10, 7), 75.0)
    add_weight(engine, date(2026, 10, 13), 74.0)
    add_weight(engine, date(2026, 10, 16), 74.5)

    row = summary(engine)

    assert (float(row.avg_weight_kg), float(row.prev_avg_weight_kg)) == (74.25, 75.0)


def test_a_recovery_day_counts_as_a_kept_day(engine):
    add_session(engine, date(2026, 10, 12), 1, minutes=30)
    add_calories(engine, date(2026, 10, 12), kcal=1800)
    add_recovery(engine, date(2026, 10, 13))

    assert summary(engine).qualifying_days == 2  # a rest day keeps the streak (Slice 7d)
