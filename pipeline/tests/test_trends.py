"""Weekly and monthly trends and the 7-day rolling average (migration 0008).

Today is Wednesday 2026-10-21 (day_builder.TODAY), so the current week is Oct 19-25.
"""

from datetime import date

from day_builder import TODAY, add_calories, add_target, date_key
from sqlalchemy import Engine, text

MON = date(2026, 10, 19)  # Monday of the current week
LAST_MON = date(2026, 10, 12)
TWO_AGO_MON = date(2026, 10, 5)


def add_session(
    engine: Engine,
    day: date,
    strava_id: int,
    minutes: int,
    sport: str = "Run",
    app_type: str = "run",
    distance_m: float | None = None,
) -> None:
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
                "VALUES (:sport, :app_type, :sport) ON CONFLICT DO NOTHING"
            ),
            {"sport": sport, "app_type": app_type},
        )
        conn.execute(
            text(
                "INSERT INTO core.fact_activity (strava_id, date_key, activity_type_key, "
                "started_at, started_local, ended_at, duration_s, distance_m, "
                "source_fetched_at) "
                "SELECT :id, :date_key, activity_type_key, CAST(:started AS timestamptz), "
                "CAST(:local AS timestamp), CAST(:started AS timestamptz), :duration, "
                ":distance, now() FROM core.dim_activity_type WHERE strava_sport_type = :sport"
            ),
            {
                "id": strava_id,
                "date_key": date_key(day),
                "started": f"{day}T08:00:00+08:00",
                "local": f"{day} 08:00",
                "duration": minutes * 60,
                "distance": distance_m,
                "sport": sport,
            },
        )


def add_lifting_set(engine: Engine, strava_id: int, number: int, weight_kg: float, reps: int):
    with engine.begin() as conn:
        exercise_key = conn.execute(
            text(
                "INSERT INTO core.dim_exercise (exercise_name, equipment, muscle_group) "
                "VALUES ('Bench Press', NULL, 'Chest') ON CONFLICT (exercise_name, equipment) "
                "DO UPDATE SET muscle_group = EXCLUDED.muscle_group RETURNING exercise_key"
            )
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO core.fact_set (activity_key, date_key, exercise_key, "
                "exercise_order, set_number, set_kind, weight_kg, reps, orig_weight, orig_unit) "
                "SELECT activity_key, date_key, :exercise_key, 1, :number, 'weight_reps', "
                ":weight, :reps, :weight, 'kg' FROM core.fact_activity WHERE strava_id = :id"
            ),
            {
                "exercise_key": exercise_key,
                "number": number,
                "weight": weight_kg,
                "reps": reps,
                "id": strava_id,
            },
        )


def add_protein(engine: Engine, day: date, grams: float) -> None:
    with engine.begin() as conn:
        batch_id = conn.execute(
            text(
                "INSERT INTO raw.health_batches (window_start, window_end, device_tz, "
                "payload_sha256, payload) VALUES (:day, :day, 'Asia/Manila', 'p', '{}') "
                "RETURNING batch_id"
            ),
            {"day": day},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO core.fact_dietary_sample (batch_id, sample_idx, date_key, "
                "local_date, sample_type, value, start_ts) VALUES (:b, 0, :key, :day, "
                "'protein', :grams, now())"
            ),
            {"b": batch_id, "key": date_key(day), "day": day, "grams": grams},
        )


def rows(engine: Engine, sql: str, **params) -> list:
    with engine.connect() as conn:
        return conn.execute(text(sql), params).all()


def training(engine: Engine, grain: str = "week", periods: int = 3, today: date = TODAY):
    return rows(
        engine,
        "SELECT * FROM mart.fn_training_trend(:today, :grain, :periods)",
        today=today,
        grain=grain,
        periods=periods,
    )


def nutrition(engine: Engine, grain: str = "week", periods: int = 3, today: date = TODAY):
    return rows(
        engine,
        "SELECT * FROM mart.fn_nutrition_trend(:today, :grain, :periods)",
        today=today,
        grain=grain,
        periods=periods,
    )


# --- periods -------------------------------------------------------------------------------


def test_weeks_run_monday_to_sunday_ending_with_the_current_week(engine):
    weeks = rows(engine, "SELECT * FROM mart.fn_periods(:today, 'week', 3)", today=TODAY)

    assert [(w.period_start, w.period_end) for w in weeks] == [
        (date(2026, 10, 5), date(2026, 10, 11)),
        (date(2026, 10, 12), date(2026, 10, 18)),
        (date(2026, 10, 19), date(2026, 10, 25)),
    ]


def test_months_are_calendar_months_and_cross_the_year(engine):
    months = rows(
        engine, "SELECT * FROM mart.fn_periods(:today, 'month', 2)", today=date(2027, 1, 15)
    )

    assert [(m.period_start, m.period_end) for m in months] == [
        (date(2026, 12, 1), date(2026, 12, 31)),
        (date(2027, 1, 1), date(2027, 1, 31)),
    ]


def test_an_unknown_grain_returns_no_periods(engine):
    assert rows(engine, "SELECT * FROM mart.fn_periods(:today, 'day', 3)", today=TODAY) == []


# --- training ------------------------------------------------------------------------------


def test_training_totals_per_week(engine):
    add_session(engine, LAST_MON, 1, minutes=30, distance_m=5000)
    add_session(engine, date(2026, 10, 15), 2, minutes=45, distance_m=7500)
    add_session(
        engine, date(2026, 10, 17), 3, minutes=60, sport="WeightTraining", app_type="strength"
    )
    add_lifting_set(engine, 3, number=1, weight_kg=20, reps=8)
    add_lifting_set(engine, 3, number=2, weight_kg=22.5, reps=6)

    last_week = training(engine)[1]

    assert (last_week.period_start, last_week.sessions, last_week.active_s) == (LAST_MON, 3, 8100)
    assert float(last_week.run_m) == 12500  # the strength session has no running distance
    assert float(last_week.volume_kg) == 295  # 20 x 8 + 22.5 x 6


def test_a_week_without_training_is_a_row_of_zeros_not_missing(engine):
    add_session(engine, MON, 1, minutes=30)

    weeks = training(engine)

    assert [(w.period_start, w.sessions, w.active_s) for w in weeks] == [
        (TWO_AGO_MON, 0, 0),
        (LAST_MON, 0, 0),
        (MON, 1, 1800),
    ]


def test_only_the_week_containing_today_is_current(engine):
    assert [w.is_current for w in training(engine)] == [False, False, True]


def test_change_uses_lag_even_for_the_oldest_week_shown(engine):
    add_session(engine, date(2026, 9, 28), 1, minutes=40)  # the hidden week before Oct 5
    add_session(engine, TWO_AGO_MON, 2, minutes=60)
    add_session(engine, LAST_MON, 3, minutes=45)

    weeks = training(engine)

    assert [(w.prev_active_s, w.active_change_pct) for w in weeks] == [
        (2400, 50),  # 60 min against 40: up 50%
        (3600, -25),  # 45 against 60: down 25%
        (2700, -100),  # nothing yet this week
    ]


def test_no_change_is_stated_after_a_week_without_training(engine):
    add_session(engine, LAST_MON, 1, minutes=45)

    oldest_two = training(engine)[:2]

    assert [w.active_change_pct for w in oldest_two] == [None, None]


def test_activities_after_today_are_left_out(engine):
    add_session(engine, date(2026, 10, 22), 1, minutes=30)  # tomorrow (a clock edge in tests)

    assert training(engine)[-1].sessions == 0


def test_monthly_training(engine):
    add_session(engine, date(2026, 9, 3), 1, minutes=30)
    add_session(engine, date(2026, 9, 30), 2, minutes=30)
    add_session(engine, date(2026, 10, 1), 3, minutes=30)

    months = training(engine, grain="month", periods=2)

    assert [(m.period_start, m.sessions, m.active_change_pct) for m in months] == [
        (date(2026, 9, 1), 2, None),
        (date(2026, 10, 1), 1, -50),
    ]


# --- nutrition -----------------------------------------------------------------------------


def test_averages_skip_days_without_food_logged(engine):
    add_target(engine, date(2026, 10, 1), budget=2000)
    add_calories(engine, LAST_MON, kcal=1800)
    add_calories(engine, date(2026, 10, 14), kcal=2200)  # five days not logged

    last_week = nutrition(engine)[1]

    assert last_week.days_logged == 2
    assert last_week.avg_kcal == 2000  # (1800 + 2200) / 2, not / 7
    assert (last_week.days_within, last_week.days_over, last_week.status) == (1, 1, "within")


def test_a_week_with_nothing_logged_is_not_logged(engine):
    weeks = nutrition(engine)

    assert [(w.days_logged, w.avg_kcal, w.status) for w in weeks] == [
        (0, None, "not_logged"),
        (0, None, "not_logged"),
        (0, None, "not_logged"),
    ]


def test_calories_without_a_budget_are_not_set(engine):
    add_calories(engine, LAST_MON, kcal=3000)

    assert nutrition(engine)[1].status == "not_set"


def test_a_budget_change_inside_a_week_is_averaged_per_logged_day(engine):
    add_target(engine, date(2026, 10, 1), budget=2000)
    add_target(engine, date(2026, 10, 15), budget=1500)
    add_calories(engine, date(2026, 10, 13), kcal=1800)  # within 2,000
    add_calories(engine, date(2026, 10, 16), kcal=1800)  # over 1,500

    last_week = nutrition(engine)[1]

    assert last_week.avg_budget == 1750
    assert (last_week.days_within, last_week.days_over, last_week.status) == (1, 1, "over")


def test_nutrition_lag_reaches_the_hidden_week(engine):
    add_calories(engine, date(2026, 9, 30), kcal=1600)  # in the hidden week of Sep 28
    add_calories(engine, TWO_AGO_MON, kcal=1900)

    assert [w.prev_avg_kcal for w in nutrition(engine)] == [1600, 1900, None]


def test_average_protein_per_logged_day(engine):
    add_protein(engine, LAST_MON, 100)
    add_protein(engine, date(2026, 10, 13), 130)

    assert nutrition(engine)[1].avg_protein_g == 115


# --- rolling average -----------------------------------------------------------------------


def rolling(engine: Engine, start: date, end: date) -> list:
    return rows(
        engine,
        "SELECT * FROM mart.fn_nutrition_rolling(:start, :end)",
        start=start,
        end=end,
    )


def test_the_rolling_average_covers_the_day_and_the_six_before(engine):
    add_calories(engine, date(2026, 10, 13), kcal=1000)  # 7 days before Oct 20: outside
    add_calories(engine, date(2026, 10, 14), kcal=1500)  # first day inside
    add_calories(engine, date(2026, 10, 20), kcal=2500)

    (oct_20,) = rolling(engine, date(2026, 10, 20), date(2026, 10, 20))

    assert (oct_20.kcal_avg_7d, oct_20.days_logged_7d) == (2000, 2)


def test_the_rolling_average_reads_days_before_the_range(engine):
    add_calories(engine, date(2026, 10, 10), kcal=1800)

    days = rolling(engine, date(2026, 10, 15), date(2026, 10, 17))

    assert [(d.day, d.kcal_avg_7d) for d in days] == [
        (date(2026, 10, 15), 1800),
        (date(2026, 10, 16), 1800),
        (date(2026, 10, 17), None),  # Oct 10 has left the window
    ]


def test_the_rolling_protein_average(engine):
    add_protein(engine, date(2026, 10, 19), 100)
    add_protein(engine, date(2026, 10, 20), 121)

    (oct_20,) = rolling(engine, date(2026, 10, 20), date(2026, 10, 20))

    assert oct_20.protein_avg_7d == 111  # 110.5 rounds half up in numeric
