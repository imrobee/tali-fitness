"""GET /api/v1/calendar (clock frozen at Tue 2026-10-20)."""

from datetime import date

from builders import add_activity, add_recovery, qualify


def get(client, query: str = ""):
    return client.get(f"/api/v1/calendar{query}")


def test_the_month_grid_is_full_monday_to_sunday_weeks(client):
    body = get(client).json()

    # October 2026 starts on a Thursday and ends on a Saturday.
    assert (body["view"], body["period_start"], body["period_end"]) == (
        "month",
        "2026-10-01",
        "2026-10-31",
    )
    assert (body["days"][0]["date"], body["days"][-1]["date"], len(body["days"])) == (
        "2026-09-28",
        "2026-11-01",
        35,
    )
    assert [d["in_period"] for d in body["days"][:4]] == [False, False, False, True]


def test_days_after_today_are_future(client):
    days = {d["date"]: d for d in get(client).json()["days"]}

    assert (days["2026-10-20"]["future"], days["2026-10-21"]["future"]) == (False, True)


def test_each_day_has_its_count_and_the_longest_activitys_type(client, engine):
    add_activity(engine, date(2026, 10, 14), local_time="07:00", duration_s=1800)
    add_activity(
        engine,
        date(2026, 10, 14),
        sport="WeightTraining",
        app_type="strength",
        local_time="17:00",
        duration_s=3600,
    )

    oct_14 = next(d for d in get(client).json()["days"] if d["date"] == "2026-10-14")

    assert (oct_14["activity_count"], oct_14["primary_activity_type"]) == (2, "strength")


def test_a_valid_recovery_day_is_marked(client, engine):
    qualify(engine, date(2026, 10, 18))
    add_recovery(engine, date(2026, 10, 19))

    days = {d["date"]: d for d in get(client).json()["days"]}

    assert (days["2026-10-19"]["recovery"], days["2026-10-18"]["recovery"]) == (True, False)


def test_previous_stops_at_the_first_month_with_data_and_next_at_today(client, engine):
    add_activity(engine, date(2026, 9, 15))

    october = get(client).json()
    september = get(client, "?date=2026-09-10").json()

    assert (october["previous"], october["next"]) == ("2026-09-01", None)
    assert (september["previous"], september["next"]) == (None, "2026-10-01")


def test_the_week_view(client, engine):
    add_activity(engine, date(2026, 10, 1))

    body = get(client, "?view=week&date=2026-10-14").json()

    assert (body["period_start"], body["period_end"], len(body["days"])) == (
        "2026-10-12",
        "2026-10-18",
        7,
    )
    assert (body["previous"], body["next"]) == ("2026-10-05", "2026-10-19")
    assert all(d["in_period"] for d in body["days"])


def test_a_future_date_or_one_before_the_data_is_out_of_range(client, engine):
    add_activity(engine, date(2026, 9, 15))

    future = get(client, "?date=2026-10-21")
    too_early = get(client, "?date=2026-08-31")

    assert future.status_code == too_early.status_code == 422
    assert future.json()["error"]["code"] == "date_out_of_range"
    assert too_early.json()["error"]["code"] == "date_out_of_range"


def test_an_unknown_view_is_invalid(client):
    response = get(client, "?view=year")

    assert (response.status_code, response.json()["error"]["code"]) == (422, "invalid_payload")


def test_the_week_of_today_is_the_default(client):
    assert get(client, "?view=week").json()["period_start"] == "2026-10-19"


def test_the_calendar_needs_sign_in(anonymous):
    assert anonymous.get("/api/v1/calendar").status_code == 401
