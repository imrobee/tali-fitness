"""GET /api/v1/dashboard against real Postgres, with the clock frozen at Tue 2026-10-20 20:00."""

from datetime import timedelta

from builders import TODAY, add_activity, add_food, add_recovery, add_target, qualify

YESTERDAY = TODAY - timedelta(days=1)
MONDAY = TODAY - timedelta(days=1)  # TODAY is a Tuesday


def get(client, query: str = ""):
    return client.get(f"/api/v1/dashboard{query}")


def test_requires_sign_in(anonymous):
    assert anonymous.get("/api/v1/dashboard").status_code == 401


def test_an_empty_database_still_returns_a_full_dashboard(client):
    body = get(client).json()

    assert body["today"] == body["selected_date"] == body["earliest_date"] == "2026-10-20"
    assert body["greeting"] == "Good evening"  # 20:00 local
    assert body["streak"]["count"] == 0
    assert [d["weekday"] for d in body["streak"]["week"]] == list("MTWTFSS")
    assert body["recovery"] == {"state": "available"}
    assert body["exercises"] == []
    assert body["calories"] == {
        "eaten": 0,
        "budget": None,
        "remaining": None,
        "over": None,
        "status": "not_logged",
    }
    assert body["protein"] == {"grams": 0, "goal": None, "percent": None}


def test_streak_week_states_icons_and_markers(client, engine):
    add_target(engine, TODAY - timedelta(days=30), budget=1853)
    add_activity(engine, MONDAY, sport="WeightTraining", app_type="strength", duration_s=3600)
    add_activity(engine, MONDAY, local_time="06:00", duration_s=1200)  # shorter run
    add_food(engine, MONDAY, kcal=2173)  # over budget

    week = get(client).json()["streak"]["week"]

    assert week[0] == {
        "date": "2026-10-19",
        "weekday": "M",
        "state": "counted",
        "kind": "over",  # a workout, over budget: fine once
        "recovery_logged": False,
        "primary_activity_type": "strength",  # the longest activity that day
        "calorie_status": "over",
        "in_streak": True,  # counted, in the current streak
    }
    assert (week[1]["state"], week[1]["kind"]) == ("pending", "miss")
    assert not week[1]["in_streak"]  # today doesn't count yet: a gap in the string
    assert {d["state"] for d in week[2:]} == {"future"}


def test_calories_and_protein_cards_for_the_selected_day(client, engine):
    add_target(engine, TODAY - timedelta(days=30), budget=1853, protein=130)
    add_food(engine, TODAY, kcal=654, protein=21)

    body = get(client).json()

    assert body["calories"] == {
        "eaten": 654,
        "budget": 1853,
        "remaining": 1199,
        "over": 0,
        "status": "within",
    }
    assert body["protein"] == {"grams": 21, "goal": 130, "percent": 16}


def test_over_budget_shows_the_overage_and_no_remaining(client, engine):
    add_target(engine, TODAY - timedelta(days=30), budget=1853)
    add_food(engine, TODAY, kcal=2173)

    calories = get(client).json()["calories"]

    assert (calories["remaining"], calories["over"], calories["status"]) == (0, 320, "over")


def test_exercises_are_most_recent_first_with_local_times(client, engine):
    add_activity(engine, TODAY, title="Morning Run", local_time="06:30")
    add_activity(
        engine,
        TODAY,
        sport="WeightTraining",
        app_type="strength",
        title="Full Body",
        local_time="16:39",
        duration_s=4069,
    )

    exercises = get(client).json()["exercises"]

    assert [e["title"] for e in exercises] == ["Full Body", "Morning Run"]
    assert exercises[0]["started_at"] == "2026-10-20T16:39:00+08:00"
    assert (exercises[0]["type"], exercises[0]["duration_s"]) == ("strength", 4069)


def test_selected_date_moves_the_cards_but_not_the_streak_week(client, engine):
    qualify(engine, YESTERDAY)
    add_food(engine, TODAY - timedelta(days=7), kcal=900)  # previous week

    body = get(client, "?date=2026-10-13").json()

    assert body["selected_date"] == "2026-10-13"
    assert body["calories"]["eaten"] == 900
    assert body["week_chart"]["week_start"] == "2026-10-12"
    assert body["streak"]["week"][0]["date"] == "2026-10-19"  # still the current week
    assert body["recovery"]["state"] == "locked"


def test_week_chart_has_no_bar_for_future_or_unlogged_days(client, engine):
    add_target(engine, TODAY - timedelta(days=30), budget=1853)
    add_food(engine, MONDAY, kcal=1500)

    bars = get(client).json()["week_chart"]["bars"]

    assert bars[0] == {"date": "2026-10-19", "kcal": 1500, "budget": 1853, "status": "within"}
    assert (bars[1]["kcal"], bars[1]["status"]) == (None, "not_logged")
    assert {(b["kcal"], b["status"]) for b in bars[2:]} == {(None, "future")}


def test_a_date_after_today_or_before_the_data_is_out_of_range(client, engine):
    qualify(engine, YESTERDAY)

    assert get(client, "?date=2026-10-21").json()["error"]["code"] == "date_out_of_range"
    assert get(client, "?date=2026-10-01").json()["error"]["code"] == "date_out_of_range"
    assert get(client, "?date=not-a-date").json()["error"]["code"] == "invalid_payload"


def test_at_risk_message(client, engine):
    qualify(engine, TODAY - timedelta(days=3))
    qualify(engine, TODAY - timedelta(days=2))

    streak = get(client).json()["streak"]

    assert (streak["count"], streak["at_risk"]) == (2, True)
    assert streak["message"] == "Yesterday isn't logged. Fill it in to keep your 2-day streak."


def test_counted_message(client, engine):
    qualify(engine, TODAY)

    assert get(client).json()["streak"]["message"] == "Nice. Today's counted."


def test_fresh_start_message_after_a_broken_streak(client, engine):
    for days_ago in (6, 5, 4):
        qualify(engine, TODAY - timedelta(days=days_ago))

    streak = get(client).json()["streak"]

    assert streak["count"] == 0
    assert streak["message"] == "Fresh start today. Your best was 3 days."


def test_recovery_card_states(client, engine):
    qualify(engine, TODAY - timedelta(days=2))
    add_recovery(engine, YESTERDAY)

    assert get(client, "?date=2026-10-19").json()["recovery"]["state"] == "logged"
    # Yesterday is a rest day, so a rest day today would be a second one in a row.
    assert get(client).json()["recovery"]["state"] == "blocked"


def test_the_week_tells_a_logged_recovery_day_from_a_day_without_a_workout(client, engine):
    add_target(engine, TODAY - timedelta(days=30), budget=1853)
    add_food(engine, YESTERDAY, kcal=1500)  # food, no workout: a rest day by the rules
    add_recovery(engine, TODAY)  # logged by hand

    week = get(client).json()["streak"]["week"]

    assert (week[0]["kind"], week[0]["recovery_logged"]) == ("recovery", False)
    assert (week[1]["kind"], week[1]["recovery_logged"]) == ("recovery", True)


def test_the_week_strings_together_the_days_of_the_current_streak(client, engine):
    qualify(engine, MONDAY)
    qualify(engine, TODAY)

    week = get(client).json()["streak"]["week"]

    assert [day["in_streak"] for day in week] == [True, True, False, False, False, False, False]


def test_nickname_shows_once_set(client):
    client.put("/api/v1/me", json={"nickname": "Rob"})

    assert get(client).json()["nickname"] == "Rob"


def test_the_streak_card_says_why_today_is_not_counted_yet(client, engine):
    qualify(engine, TODAY - timedelta(days=2))
    add_food(engine, YESTERDAY)  # a rest day
    add_food(engine, TODAY)  # food so far, no workout: a second rest day if it stays so

    streak = get(client).json()["streak"]

    assert streak["count"] == 2
    assert streak["message"] == "Yesterday was a rest day. A workout today keeps your streak going."


def test_the_streak_card_names_a_second_over_day_yesterday(client, engine):
    add_target(engine, TODAY - timedelta(days=30), budget=1853)
    qualify(engine, TODAY - timedelta(days=3))
    add_activity(engine, TODAY - timedelta(days=2))
    add_food(engine, TODAY - timedelta(days=2), kcal=2200)
    add_activity(engine, YESTERDAY)
    add_food(engine, YESTERDAY, kcal=2300)

    streak = get(client).json()["streak"]

    assert (streak["count"], streak["at_risk"]) == (2, True)
    assert streak["message"].startswith("Yesterday was a second day over budget.")
