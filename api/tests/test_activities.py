"""GET /api/v1/activities and GET /api/v1/activities/{id} (clock frozen at Tue 2026-10-20)."""

from datetime import timedelta

from builders import TODAY, add_activity, date_key
from sqlalchemy import Engine, text


def add_set(engine: Engine, strava_id: int, order: int, number: int, kind: str, **measures):
    """One set on an activity. Each exercise order gets its own exercise, named by order."""
    with engine.begin() as conn:
        exercise_key = conn.execute(
            text(
                "INSERT INTO core.dim_exercise (exercise_name, equipment, muscle_group) "
                "VALUES (:name, NULL, 'Chest') ON CONFLICT (exercise_name, equipment) "
                "DO UPDATE SET muscle_group = EXCLUDED.muscle_group RETURNING exercise_key"
            ),
            {"name": f"Exercise {order}"},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO core.fact_set (activity_key, date_key, exercise_key, exercise_order, "
                "set_number, set_kind, weight_kg, reps, distance_m, duration_s, orig_weight, "
                "orig_unit, exercise_note) "
                # Only weight sets carry the entered weight and unit (the set-kind CHECK).
                "SELECT activity_key, date_key, :exercise_key, :order, :number, :kind, "
                "CAST(:weight AS numeric), :reps, :distance, :duration, "
                "CASE WHEN :kind = 'weight_reps' THEN CAST(:weight AS numeric) END, "
                "CASE WHEN :kind = 'weight_reps' THEN 'kg' END, :note "
                "FROM core.fact_activity WHERE strava_id = :id"
            ),
            {
                "exercise_key": exercise_key,
                "order": order,
                "number": number,
                "kind": kind,
                "weight": measures.get("weight_kg"),
                "reps": measures.get("reps"),
                "distance": measures.get("distance_m"),
                "duration": measures.get("duration_s"),
                "note": measures.get("note"),
                "id": strava_id,
            },
        )


def activity_id(engine: Engine, strava_id: int) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT activity_key FROM core.fact_activity WHERE strava_id = :id"),
            {"id": strava_id},
        ).scalar_one()


def strava_id_for(day, local_time="17:00") -> int:
    """The id add_activity gives an activity at this local time (see builders.py)."""
    return date_key(day) * 10 + int(local_time[:2]) // 3


# --- list ----------------------------------------------------------------------------------


def test_the_list_is_grouped_by_day_newest_first(client, engine):
    add_activity(engine, TODAY, title="Morning Run", local_time="07:00")
    add_activity(engine, TODAY, title="Evening Run", local_time="18:00")
    add_activity(engine, TODAY - timedelta(days=1), title="Yesterday Run")

    body = client.get("/api/v1/activities").json()

    assert [day["date"] for day in body["days"]] == ["2026-10-20", "2026-10-19"]
    assert [a["title"] for a in body["days"][0]["activities"]] == ["Evening Run", "Morning Run"]


def test_the_default_range_is_the_last_30_days(client, engine):
    add_activity(engine, TODAY - timedelta(days=29), title="Inside")
    add_activity(engine, TODAY - timedelta(days=30), title="Outside")

    body = client.get("/api/v1/activities").json()

    assert (body["from"], body["to"]) == ("2026-09-21", "2026-10-20")
    titles = [a["title"] for day in body["days"] for a in day["activities"]]
    assert titles == ["Inside"]


def test_an_explicit_range_is_honoured(client, engine):
    add_activity(engine, TODAY - timedelta(days=5), title="Wanted")
    add_activity(engine, TODAY - timedelta(days=50), title="Not wanted")

    body = client.get(
        "/api/v1/activities",
        params={"from": "2026-10-10", "to": "2026-10-15"},
    ).json()

    assert [a["title"] for day in body["days"] for a in day["activities"]] == ["Wanted"]


def test_strength_summary_counts_exercises_sets_and_volume(client, engine):
    add_activity(engine, TODAY, sport="WeightTraining", app_type="strength", local_time="10:00")
    strava_id = strava_id_for(TODAY, "10:00")
    add_set(engine, strava_id, 1, 1, "weight_reps", weight_kg=20, reps=8)
    add_set(engine, strava_id, 1, 2, "weight_reps", weight_kg=20, reps=8)
    add_set(engine, strava_id, 2, 1, "reps", reps=15)

    summary = client.get("/api/v1/activities").json()["days"][0]["activities"][0]

    assert (summary["exercise_count"], summary["set_count"]) == (2, 3)
    assert summary["volume_kg"] == 320.0  # 20 kg x 8 x 2; bodyweight sets add nothing


def test_a_run_has_no_sets_and_no_volume(client, engine):
    add_activity(engine, TODAY)

    summary = client.get("/api/v1/activities").json()["days"][0]["activities"][0]

    assert (summary["exercise_count"], summary["set_count"], summary["volume_kg"]) == (0, 0, 0.0)
    assert summary["moving_s"] is None  # the test helper sets no moving time


def test_a_range_over_a_year_is_refused(client):
    response = client.get("/api/v1/activities", params={"from": "2025-01-01", "to": "2026-10-20"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "date_out_of_range"


def test_from_after_to_is_refused(client):
    response = client.get("/api/v1/activities", params={"from": "2026-10-20", "to": "2026-10-01"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_payload"


# --- detail --------------------------------------------------------------------------------


def test_detail_groups_sets_under_their_exercise_in_order(client, engine):
    add_activity(engine, TODAY, sport="WeightTraining", app_type="strength", local_time="10:00")
    strava_id = strava_id_for(TODAY, "10:00")
    add_set(engine, strava_id, 1, 1, "weight_reps", weight_kg=20, reps=8, note="Pause at the top")
    add_set(engine, strava_id, 1, 2, "weight_reps", weight_kg=22.5, reps=6, note="Pause at the top")
    add_set(engine, strava_id, 2, 1, "duration", duration_s=90)

    body = client.get(f"/api/v1/activities/{activity_id(engine, strava_id)}")
    detail = body.json()

    assert body.status_code == 200
    assert [e["name"] for e in detail["exercises"]] == ["Exercise 1", "Exercise 2"]
    assert [s["weight_kg"] for s in detail["exercises"][0]["sets"]] == [20.0, 22.5]
    assert detail["exercises"][0]["note"] == "Pause at the top"
    assert detail["exercises"][1]["sets"] == [
        {
            "number": 1,
            "kind": "duration",
            "weight_kg": None,
            "orig_weight": None,
            "orig_unit": None,
            "reps": None,
            "distance_m": None,
            "duration_s": 90,
        }
    ]


def test_raw_text_is_shown_only_when_the_parse_is_not_ok(client, engine):
    add_activity(engine, TODAY, local_time="10:00")
    strava_id = strava_id_for(TODAY, "10:00")
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE core.fact_activity SET parse_status = 'partial', "
                "description_raw = :raw WHERE strava_id = :id"
            ),
            {"raw": "Bench 3x8\nGarbage line", "id": strava_id},
        )

    detail = client.get(f"/api/v1/activities/{activity_id(engine, strava_id)}").json()

    assert detail["parse_status"] == "partial"
    assert detail["description_raw"] == "Bench 3x8\nGarbage line"


def test_raw_text_is_hidden_when_the_parse_is_ok(client, engine):
    add_activity(engine, TODAY, local_time="10:00")
    strava_id = strava_id_for(TODAY, "10:00")
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE core.fact_activity SET parse_status = 'ok', "
                "description_raw = 'Bench 3x8' WHERE strava_id = :id"
            ),
            {"id": strava_id},
        )

    detail = client.get(f"/api/v1/activities/{activity_id(engine, strava_id)}").json()

    assert detail["description_raw"] is None


def test_an_unknown_activity_is_not_found(client):
    response = client.get("/api/v1/activities/999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_activities_need_sign_in(anonymous):
    assert anonymous.get("/api/v1/activities").status_code == 401
