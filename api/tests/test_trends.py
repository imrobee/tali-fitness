"""GET /api/v1/trends/training and /trends/nutrition (clock frozen at Tue 2026-10-20).

The trend arithmetic itself is tested against the mart functions in
pipeline/tests/test_trends.py; these tests check what the endpoints add.
"""

from datetime import date

from builders import TODAY, add_activity, add_food, add_target
from conftest import TEST_API_KEY

HEADERS = {"X-API-Key": TEST_API_KEY}


def get(client, path: str):
    return client.get(f"/api/v1/trends/{path}", headers=HEADERS)


def test_training_shows_eight_weeks_ending_with_the_current_one(client, engine):
    add_activity(engine, TODAY, duration_s=1800)
    add_activity(engine, date(2026, 10, 14), duration_s=3600)

    periods = get(client, "training").json()["periods"]

    assert (len(periods), periods[0]["start"], periods[-1]["start"]) == (
        8,
        "2026-08-31",
        "2026-10-19",
    )
    assert [p["current"] for p in periods[-2:]] == [False, True]
    assert (periods[-1]["sessions"], periods[-1]["active_s"]) == (1, 1800)
    assert (periods[-1]["prev_active_s"], periods[-1]["active_change_pct"]) == (3600, -50)


def test_training_by_month_shows_six_months(client):
    periods = get(client, "training?grain=month").json()["periods"]

    assert [p["start"] for p in periods] == [
        "2026-05-01",
        "2026-06-01",
        "2026-07-01",
        "2026-08-01",
        "2026-09-01",
        "2026-10-01",
    ]


def test_nutrition_averages_are_whole_numbers(client, engine):
    add_target(engine, date(2026, 10, 1), budget=1853, protein=130)
    add_food(engine, date(2026, 10, 12), kcal=1800.4, protein=100.4)
    add_food(engine, date(2026, 10, 13), kcal=1900, protein=120)

    last_week = get(client, "nutrition").json()["periods"][-2]

    assert (last_week["avg_kcal"], last_week["avg_protein_g"], last_week["avg_budget"]) == (
        1850,
        110,
        1853,
    )
    assert (last_week["days_logged"], last_week["status"]) == (2, "within")


def test_the_7_day_average_ends_yesterday(client, engine):
    add_food(engine, date(2026, 10, 12), kcal=1000)  # 7 days before yesterday: outside
    add_food(engine, date(2026, 10, 14), kcal=1600, protein=100)
    add_food(engine, date(2026, 10, 19), kcal=2000, protein=120)
    add_food(engine, TODAY, kcal=300)  # today is still being logged: left out

    rolling = get(client, "nutrition").json()["rolling_7d"]

    assert rolling == {
        "end_date": "2026-10-19",
        "kcal_avg": 1800,
        "protein_avg_g": 110,
        "days_logged": 2,
    }


def test_no_food_logged_gives_empty_averages(client):
    body = get(client, "nutrition").json()

    assert body["rolling_7d"]["kcal_avg"] is None
    assert {p["status"] for p in body["periods"]} == {"not_logged"}


def test_an_unknown_grain_is_invalid(client):
    response = get(client, "training?grain=day")

    assert (response.status_code, response.json()["error"]["code"]) == (422, "invalid_payload")


def test_trends_need_the_api_key(client):
    assert client.get("/api/v1/trends/training").status_code == 401
    assert client.get("/api/v1/trends/nutrition").status_code == 401
