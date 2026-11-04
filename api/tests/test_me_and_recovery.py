"""GET/PUT /api/v1/me and POST/DELETE /api/v1/recovery (clock frozen at Tue 2026-10-20)."""

from datetime import timedelta

import pytest
from builders import TODAY, add_food, add_recovery, qualify
from sqlalchemy import text

YESTERDAY = TODAY - timedelta(days=1)


# --- /me -----------------------------------------------------------------------------------


def test_me_starts_without_nickname_or_targets(client):
    body = client.get("/api/v1/me").json()

    assert body == {
        "nickname": None,
        "timezone": "Asia/Manila",
        "targets": None,
        "weight_goal_kg": None,
        "weight_unit": "kg",
        "lenient_weekends": False,
        "vacation": None,
        "last_vacation": None,
        "earliest_date": "2026-10-20",
    }


def test_saving_targets_applies_from_today(client):
    body = client.put(
        "/api/v1/me",
        json={"nickname": "Rob", "targets": {"calorie_budget": 1853, "protein_goal": 130}},
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
    )

    body = client.put("/api/v1/me", json={"nickname": "Rob"}).json()

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
    response = client.put("/api/v1/me", json={"targets": targets})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_payload"


# --- /recovery -----------------------------------------------------------------------------


def post_recovery(client, day):
    return client.post("/api/v1/recovery", json={"date": str(day)})


def test_log_a_recovery_day_when_the_previous_day_counted(client, engine):
    qualify(engine, YESTERDAY)

    response = post_recovery(client, TODAY)

    assert response.status_code == 201
    assert response.json() == {"date": "2026-10-20", "state": "logged"}
    dashboard = client.get("/api/v1/dashboard").json()
    assert dashboard["recovery"] == {"state": "logged"}


def test_logging_the_same_day_twice_is_fine(client, engine):
    qualify(engine, YESTERDAY)
    post_recovery(client, TODAY)

    assert post_recovery(client, TODAY).status_code == 200


def test_blocked_when_the_day_before_was_a_rest_day(client, engine):
    qualify(engine, TODAY - timedelta(days=2))
    add_food(engine, YESTERDAY)  # food, no workout: a rest day

    response = post_recovery(client, TODAY)  # a second rest day in a row would break it

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "recovery_not_allowed"


def test_heal_yesterday_with_a_recovery_day(client, engine):
    qualify(engine, TODAY - timedelta(days=3))
    qualify(engine, TODAY - timedelta(days=2))
    assert client.get("/api/v1/dashboard").json()["streak"]["at_risk"] is True

    assert post_recovery(client, YESTERDAY).status_code == 201

    streak = client.get("/api/v1/dashboard").json()["streak"]
    assert (streak["count"], streak["at_risk"]) == (3, False)  # a rest day counts


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

    response = client.delete(f"/api/v1/recovery/{TODAY}")

    assert response.status_code == 204
    dashboard = client.get("/api/v1/dashboard").json()
    assert dashboard["recovery"]["state"] == "available"


def test_undo_is_limited_to_today_or_yesterday(client):
    response = client.delete("/api/v1/recovery/2026-10-01")

    assert response.json()["error"]["code"] == "recovery_not_allowed"


def test_a_recovery_day_after_a_missed_day_is_allowed(client, engine):
    qualify(engine, TODAY - timedelta(days=2))  # yesterday has nothing: already broken

    assert post_recovery(client, TODAY).status_code == 201


# --- relaxed weekends and vacation ---------------------------------------------------------


def test_relaxed_weekends_apply_from_today(client, engine):
    me = client.put("/api/v1/me", json={"lenient_weekends": True}).json()

    assert me["lenient_weekends"] is True
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT effective_from, lenient_weekends FROM app.streak_settings_history")
        ).all()
    assert [(str(r.effective_from), r.lenient_weekends) for r in rows] == [("2026-10-20", True)]


def test_a_vacation_can_be_set_changed_and_ended(client):
    me = client.put("/api/v1/vacation", json={"from": "2026-10-24", "to": "2026-11-01"}).json()
    assert me["vacation"] == {"from": "2026-10-24", "to": "2026-11-01"}

    me = client.put("/api/v1/vacation", json={"from": "2026-10-25", "to": "2026-11-02"}).json()
    assert me["vacation"] == {"from": "2026-10-25", "to": "2026-11-02"}  # changed, not added

    assert client.delete("/api/v1/vacation").status_code == 204
    assert client.get("/api/v1/me").json()["vacation"] is None


def test_a_forgotten_vacation_in_the_past_is_kept_as_history(client):
    me = client.put("/api/v1/vacation", json={"from": "2026-10-12", "to": "2026-10-15"}).json()

    assert (me["vacation"], me["last_vacation"]) == (
        None,
        {"from": "2026-10-12", "to": "2026-10-15"},
    )


def test_a_vacation_heals_the_days_it_covers(client, engine):
    qualify(engine, TODAY - timedelta(days=3))
    add_food(engine, TODAY - timedelta(days=2))
    add_food(engine, YESTERDAY)  # a second rest day in a row: at risk
    assert client.get("/api/v1/dashboard").json()["streak"]["at_risk"] is True

    client.put("/api/v1/vacation", json={"from": "2026-10-18", "to": "2026-10-19"})

    streak = client.get("/api/v1/dashboard").json()["streak"]
    assert (streak["count"], streak["at_risk"]) == (3, False)


@pytest.mark.parametrize(
    ("period", "code"),
    [
        ({"from": "2026-10-25", "to": "2026-10-24"}, "invalid_payload"),  # backwards
        ({"from": "2026-10-01", "to": "2026-12-31"}, "invalid_payload"),  # over 90 days
        ({"from": "2027-12-01", "to": "2027-12-02"}, "date_out_of_range"),  # over a year ahead
    ],
)
def test_vacation_limits(client, period, code):
    response = client.put("/api/v1/vacation", json=period)

    assert (response.status_code, response.json()["error"]["code"]) == (422, code)


def test_vacations_cannot_overlap(client):
    client.put("/api/v1/vacation", json={"from": "2026-10-12", "to": "2026-10-15"})

    response = client.put("/api/v1/vacation", json={"from": "2026-10-14", "to": "2026-10-22"})

    assert response.json()["error"]["code"] == "vacation_overlap"
