"""GET /api/v1/weight and the weight goal on PUT /api/v1/me (clock frozen at Tue 2026-10-20)."""

from datetime import date, timedelta

from builders import TODAY
from conftest import TEST_API_KEY
from sqlalchemy import Engine, text

HEADERS = {"X-API-Key": TEST_API_KEY}


def weigh(engine: Engine, day: date, kg: float) -> None:
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
                "batch_id, source) VALUES (:d, :key, :kg, CAST(:start AS timestamptz), :b, "
                "'MyNetDiary')"
            ),
            {
                "d": day,
                "key": day.year * 10000 + day.month * 100 + day.day,
                "kg": kg,
                "start": f"{day}T07:00:00+08:00",
                "b": batch_id,
            },
        )


def get(client, query: str = ""):
    return client.get(f"/api/v1/weight{query}", headers=HEADERS)


def test_the_latest_weigh_in_with_its_average_and_change(client, engine):
    for offset in range(7, 14):
        weigh(engine, TODAY - timedelta(days=offset), 76.0)
    for offset in range(0, 3):
        weigh(engine, TODAY - timedelta(days=offset), 74.0)

    body = get(client).json()

    assert (body["latest_date"], body["latest_kg"]) == ("2026-10-20", 74.0)
    assert body["avg_7d_kg"] == 74.0  # the last 7 days hold only the three 74 kg weigh-ins
    assert body["change_7d_kg"] == -2.0  # against the 76 kg week before


def test_no_weigh_ins_gives_nulls_and_not_logged_days(client):
    body = get(client, "?from=2026-10-18&to=2026-10-20").json()

    assert (body["latest_date"], body["latest_kg"], body["goal_kg"]) == (None, None, None)
    assert {d["status"] for d in body["days"]} == {"not_logged"}


def test_the_goal_is_set_from_today_and_judges_the_average(client, engine):
    weigh(engine, TODAY, 74.0)
    response = client.put("/api/v1/me", headers=HEADERS, json={"weight_goal_kg": 72.5})

    assert response.json()["weight_goal_kg"] == 72.5
    body = get(client, "?from=2026-10-20&to=2026-10-20").json()
    assert (body["goal_kg"], body["to_goal_kg"]) == (72.5, 1.5)
    assert body["days"][0]["status"] == "above"


def test_saving_other_fields_keeps_the_weight_goal(client):
    client.put("/api/v1/me", headers=HEADERS, json={"weight_goal_kg": 72.5})

    me = client.put("/api/v1/me", headers=HEADERS, json={"nickname": "Rob"}).json()

    assert me["weight_goal_kg"] == 72.5


def test_a_goal_outside_the_sanity_range_is_refused(client):
    response = client.put("/api/v1/me", headers=HEADERS, json={"weight_goal_kg": 5})

    assert (response.status_code, response.json()["error"]["code"]) == (422, "invalid_payload")


def test_the_range_is_limited_and_must_run_forwards(client):
    too_long = get(client, "?from=2024-01-01&to=2026-10-20")
    backwards = get(client, "?from=2026-10-20&to=2026-10-01")

    assert too_long.json()["error"]["code"] == "date_out_of_range"
    assert backwards.json()["error"]["code"] == "invalid_payload"


def test_the_weight_needs_the_api_key(client):
    assert client.get("/api/v1/weight").status_code == 401


# --- the unit preference -------------------------------------------------------------------


def test_the_unit_starts_as_kg_and_can_change_to_lb(client):
    assert client.get("/api/v1/me", headers=HEADERS).json()["weight_unit"] == "kg"

    me = client.put("/api/v1/me", headers=HEADERS, json={"weight_unit": "lb"}).json()

    assert me["weight_unit"] == "lb"
    assert client.get("/api/v1/me", headers=HEADERS).json()["weight_unit"] == "lb"


def test_changing_the_unit_never_changes_stored_weights(client, engine):
    weigh(engine, TODAY, 74.84274105)
    client.put("/api/v1/me", headers=HEADERS, json={"weight_goal_kg": 72.5747792})

    client.put("/api/v1/me", headers=HEADERS, json={"weight_unit": "lb"})
    body = get(client, "?from=2026-10-20&to=2026-10-20").json()

    assert body["latest_kg"] == 74.84274105  # still kg: the page converts for display
    assert body["goal_kg"] == 72.575  # 160 lb, stored to 3 decimals so it reads back as 160.0


def test_an_unknown_unit_is_refused(client):
    response = client.put("/api/v1/me", headers=HEADERS, json={"weight_unit": "stone"})

    assert (response.status_code, response.json()["error"]["code"]) == (422, "invalid_payload")
