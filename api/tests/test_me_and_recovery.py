"""GET/PUT /api/v1/me and POST/DELETE /api/v1/recovery (clock frozen at Tue 2026-10-20)."""

from datetime import timedelta

import pytest
from builders import TODAY, add_recovery, qualify
from conftest import TEST_API_KEY
from sqlalchemy import text

HEADERS = {"X-API-Key": TEST_API_KEY}
YESTERDAY = TODAY - timedelta(days=1)


# --- /me -----------------------------------------------------------------------------------


def test_me_starts_without_nickname_or_targets(client):
    body = client.get("/api/v1/me", headers=HEADERS).json()

    assert body == {
        "nickname": None,
        "timezone": "Asia/Manila",
        "targets": None,
        "weight_goal_kg": None,
        "weight_unit": "kg",
        "earliest_date": "2026-10-20",
    }


def test_saving_targets_applies_from_today(client):
    body = client.put(
        "/api/v1/me",
        json={"nickname": "Rob", "targets": {"calorie_budget": 1853, "protein_goal": 130}},
        headers=HEADERS,
    ).json()

    assert body["nickname"] == "Rob"
    assert body["targets"] == {
        "calorie_budget": 1853,
        "protein_goal": 130,
        "effective_from": "2026-10-20",
    }


def test_saving_twice_on_one_day_replaces_that_days_targets(client, engine):
    for budget in (1853, 2000):
        client.put(
            "/api/v1/me",
            json={"targets": {"calorie_budget": budget, "protein_goal": 130}},
            headers=HEADERS,
        )

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT calorie_budget FROM app.target_history")).all()
    assert [r.calorie_budget for r in rows] == [2000]


def test_earlier_targets_stay_in_history(client, engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO app.target_history (effective_from, calorie_budget, protein_goal) "
                "VALUES ('2026-10-01', 2200, 120)"
            )
        )

    client.put(
        "/api/v1/me",
        json={"targets": {"calorie_budget": 1853, "protein_goal": 130}},
        headers=HEADERS,
    )

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT effective_from::text, calorie_budget FROM app.target_history ORDER BY 1")
        ).all()
    assert [tuple(r) for r in rows] == [("2026-10-01", 2200), ("2026-10-20", 1853)]


def test_updating_only_the_nickname_keeps_the_targets(client):
    client.put(
        "/api/v1/me",
        json={"targets": {"calorie_budget": 1853, "protein_goal": 130}},
        headers=HEADERS,
    )

    body = client.put("/api/v1/me", json={"nickname": "Rob"}, headers=HEADERS).json()

    assert body["targets"]["calorie_budget"] == 1853


@pytest.mark.parametrize(
    "targets",
    [
        {"calorie_budget": 799, "protein_goal": 130},
        {"calorie_budget": 6001, "protein_goal": 130},
        {"calorie_budget": 1853, "protein_goal": 401},
        {"calorie_budget": 1853},
    ],
)
def test_targets_outside_the_sanity_limits_are_rejected(client, targets):
    response = client.put("/api/v1/me", json={"targets": targets}, headers=HEADERS)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_payload"


# --- /recovery -----------------------------------------------------------------------------


def post_recovery(client, day):
    return client.post("/api/v1/recovery", json={"date": str(day)}, headers=HEADERS)


def test_log_a_recovery_day_when_the_previous_day_counted(client, engine):
    qualify(engine, YESTERDAY)

    response = post_recovery(client, TODAY)

    assert response.status_code == 201
    assert response.json() == {"date": "2026-10-20", "state": "logged"}
    dashboard = client.get("/api/v1/dashboard", headers=HEADERS).json()
    assert dashboard["recovery"] == {"state": "logged", "freezes_left": 0, "freezes_max": 1}


def test_logging_the_same_day_twice_is_fine(client, engine):
    qualify(engine, YESTERDAY)
    post_recovery(client, TODAY)

    assert post_recovery(client, TODAY).status_code == 200


def test_blocked_when_the_previous_day_did_not_count(client, engine):
    qualify(engine, TODAY - timedelta(days=2))  # yesterday has nothing

    response = post_recovery(client, TODAY)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "recovery_not_allowed"


def test_heal_yesterday_with_the_freeze(client, engine):
    qualify(engine, TODAY - timedelta(days=3))
    qualify(engine, TODAY - timedelta(days=2))
    assert client.get("/api/v1/dashboard", headers=HEADERS).json()["streak"]["at_risk"] is True

    assert post_recovery(client, YESTERDAY).status_code == 201

    streak = client.get("/api/v1/dashboard", headers=HEADERS).json()["streak"]
    assert (streak["count"], streak["at_risk"]) == (2, False)


@pytest.mark.parametrize("days_ago", [2, -1])
def test_only_today_or_yesterday(client, engine, days_ago):
    qualify(engine, TODAY - timedelta(days=days_ago + 1))

    response = post_recovery(client, TODAY - timedelta(days=days_ago))

    assert response.json()["error"]["code"] == "recovery_not_allowed"


def test_a_day_that_already_counts_needs_no_recovery(client, engine):
    qualify(engine, YESTERDAY)
    qualify(engine, TODAY)

    assert post_recovery(client, TODAY).json()["error"]["code"] == "recovery_not_allowed"


def test_undo_removes_the_recovery_day(client, engine):
    qualify(engine, YESTERDAY)
    add_recovery(engine, TODAY)

    response = client.delete(f"/api/v1/recovery/{TODAY}", headers=HEADERS)

    assert response.status_code == 204
    dashboard = client.get("/api/v1/dashboard", headers=HEADERS).json()
    assert dashboard["recovery"]["state"] == "available"


def test_undo_is_limited_to_today_or_yesterday(client):
    response = client.delete("/api/v1/recovery/2026-10-01", headers=HEADERS)

    assert response.json()["error"]["code"] == "recovery_not_allowed"
