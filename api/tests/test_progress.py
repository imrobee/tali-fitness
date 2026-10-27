"""GET /records, /muscle-volume and /summary/week (clock frozen at Tue 2026-10-20).

The arithmetic is tested against the mart functions in
pipeline/tests/test_records_volume_summary.py; these tests check what the endpoints add.
"""

from datetime import date

from builders import add_activity, add_food
from conftest import TEST_API_KEY
from sqlalchemy import text
from test_activities import add_set, strava_id_for

HEADERS = {"X-API-Key": TEST_API_KEY}


def lifting(engine, day: date) -> int:
    add_activity(engine, day, sport="WeightTraining", app_type="strength")
    return strava_id_for(day)


def get(client, path: str) -> dict:
    return client.get(f"/api/v1/{path}", headers=HEADERS).json()


def test_records_mark_a_record_from_the_last_14_days_as_recent(client, engine):
    add_set(engine, lifting(engine, date(2026, 9, 1)), 1, 1, "weight_reps", weight_kg=40, reps=8)
    add_set(engine, lifting(engine, date(2026, 10, 13)), 2, 1, "weight_reps", weight_kg=50, reps=5)

    records = {r["exercise"]: r for r in get(client, "records")["records"]}

    assert (records["Exercise 1"]["recent"], records["Exercise 2"]["recent"]) == (False, True)
    assert (records["Exercise 2"]["e1rm_kg"], records["Exercise 2"]["muscle_group"]) == (
        58.33,
        "Chest",
    )


def test_muscle_volume_is_last_finished_week_with_the_week_before(client, engine):
    add_set(engine, lifting(engine, date(2026, 10, 6)), 1, 1, "weight_reps", weight_kg=50, reps=10)
    session = lifting(engine, date(2026, 10, 14))
    add_set(engine, session, 1, 1, "weight_reps", weight_kg=50, reps=10)
    add_set(engine, session, 1, 2, "weight_reps", weight_kg=50, reps=10)
    add_set(engine, lifting(engine, date(2026, 10, 19)), 1, 1, "weight_reps", weight_kg=99, reps=1)

    body = get(client, "muscle-volume")

    assert (body["week_start"], body["week_end"]) == ("2026-10-12", "2026-10-18")
    assert body["groups"] == [
        {
            "muscle_group": "Chest",
            "sets": 2,
            "volume_kg": 1000.0,
            "prev_sets": 1,
            "prev_volume_kg": 500.0,
        }
    ]


def test_muscle_volume_leaves_out_groups_untrained_in_both_weeks(client):
    assert get(client, "muscle-volume")["groups"] == []


def test_the_weekly_summary_compares_last_week_with_the_week_before(client, engine):
    add_activity(engine, date(2026, 10, 6))
    add_food(engine, date(2026, 10, 6), kcal=1700, protein=100)
    add_activity(engine, date(2026, 10, 13))
    add_food(engine, date(2026, 10, 13), kcal=1900, protein=120)
    add_activity(engine, date(2026, 10, 14))

    body = get(client, "summary/week")

    assert (body["week_start"], body["sessions"], body["prev_sessions"]) == ("2026-10-12", 2, 1)
    # Counted days: Oct 13 (success) and Oct 14 (a workout without food: a rest day).
    assert (body["qualifying_days"], body["prev_qualifying_days"]) == (2, 1)
    assert (body["avg_kcal"], body["prev_avg_kcal"], body["avg_protein_g"]) == (1900, 1700, 120)


def test_progress_needs_the_api_key(client):
    for path in ("records", "muscle-volume", "summary/week"):
        assert client.get(f"/api/v1/{path}").status_code == 401


def test_unmapped_exercises_are_left_out_of_muscle_volume_and_unnamed_in_records(client, engine):
    session = lifting(engine, date(2026, 10, 14))
    add_set(engine, session, 1, 1, "weight_reps", weight_kg=100, reps=10)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE core.dim_exercise SET muscle_group = 'Unmapped' "
                "WHERE exercise_name = 'Exercise 1'"
            )
        )

    assert get(client, "muscle-volume")["groups"] == []
    assert get(client, "records")["records"][0]["muscle_group"] is None
