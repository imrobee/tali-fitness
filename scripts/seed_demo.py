"""Load a demo scenario into the demo database (UI_SPEC.md section 11).

Usage (inside the api-demo container; see `make seed-demo` and `make screenshots`):
    python /scripts/seed_demo.py midweek | at_risk | edge_empty

Safety: it only ever touches a database whose name ends in "_demo". It drops and
recreates that database, migrates it, and inserts one scenario. The real warehouse is
never touched. The demo API runs with NOW_OVERRIDE=2026-10-17T14:00:00+08:00 (a
Saturday afternoon), so every scenario is written relative to that day.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import TextClause, create_engine, text
from sqlalchemy.engine import make_url

TODAY = date(2026, 10, 17)  # Saturday; matches NOW_OVERRIDE of the demo API
TARGET = {"budget": 1853, "protein": 130}

SPORTS = [  # strava sport_type, app_type, label
    ("Run", "run", "Run"),
    ("Walk", "walk", "Walk"),
    ("WeightTraining", "strength", "Weight training"),
]

# Exercises for the demo's Saturday "Full Body" session, so the Activities page has sets to
# expand. Invented demo values in the shape of the Hevy sample, not Rob's workout.
# A set is (kind, weight, unit, reps, seconds); weight is in the unit given (lb is converted).
FULL_BODY = [
    {
        "name": "Incline Bench Press",
        "equipment": "Dumbbell",
        "muscle": "Chest",
        "note": None,
        "sets": [("weight_reps", 20, "kg", 8, None), ("weight_reps", 22.5, "kg", 6, None)],
    },
    {
        "name": "Lat Pulldown",
        "equipment": "Cable",
        "muscle": "Back",
        "note": "Squeeze at the bottom",
        "sets": [("weight_reps", 40, "lb", 12, None)],
    },
    {
        "name": "Goblet Squat",
        "equipment": "Kettlebell",
        "muscle": "Quads",
        "note": None,
        "sets": [("reps", None, None, 15, None)],
    },
    {
        "name": "Plank",
        "equipment": None,
        "muscle": "Core",
        "note": None,
        "sets": [("duration", None, None, None, 90)],
    },
]


def upper_body(day: date) -> list:
    """Invented sets for the history's Upper Body sessions, a little heavier every three
    weeks from May, so the demo has personal records and muscle volume to show."""
    step = (day - date(2026, 5, 5)).days // 21
    return [
        {
            "name": "Incline Bench Press",
            "equipment": "Dumbbell",
            "muscle": "Chest",
            "note": None,
            "sets": [("weight_reps", 15 + 1.25 * step, "kg", 8, None)] * 3,
        },
        {
            "name": "Lat Pulldown",
            "equipment": "Cable",
            "muscle": "Back",
            "note": None,
            "sets": [("weight_reps", 30 + 2.5 * step, "lb", 12, None)] * 3,
        },
        {
            "name": "Lateral Raise",
            "equipment": "Dumbbell",
            "muscle": "Shoulders",
            "note": None,
            "sets": [("weight_reps", 5 + 0.5 * (step // 2), "kg", 12, None)] * 2,
        },
    ]


# The Me page's "Data and sync" panel (UI_SPEC.md 11: a healthy pipeline and a stale/failed
# one). Times are hours before the demo's frozen "now" (Sat 2026-10-17 14:00 Manila).
NOW = "2026-10-17T14:00:00+08:00"
DQ_CHECKS = [
    "strava_freshness",
    "health_freshness",
    "activity_unique",
    "activity_not_null",
    "activity_duration_range",
    "set_range",
    "calorie_daily_range",
    "fk_integrity",
    "row_reconcile",
    "hevy_parse_coverage",
    "quarantine_open",
    "unmapped_exercises",
    "possible_duplicate_activity",
    "target_present",
    "days_with_activity_no_calories",
]
HEALTHY = {
    # (source, hours ago, status, error)
    "runs": [("strava", 0.7, "success", None), ("health", 0.9, "success", None)],
    "dq": {},  # every check passes
    "quarantine": [],
}
STALE = {
    "runs": [
        ("strava", 9, "success", None),
        ("health", 120, "success", None),
        ("health", 2, "failed", "Shortcut payload had no samples"),
    ],
    "dq": {"strava_freshness": "warn", "health_freshness": "fail", "quarantine_open": "warn"},
    "quarantine": [("Set 1: 20 kg x 8 @ RPE 8", 4), ("Superset A1: Curl", 7)],
}

# A scenario is a list of days: (date, activities, food).
# activity = (sport, title, local start "HH:MM", minutes); food = (kcal, protein grams).


def days_ago(n: int) -> date:
    return TODAY - timedelta(days=n)


def steady_week(first: int, last: int) -> list:
    """Qualifying days from `first` to `last` days ago: a run and a normal day of food."""
    return [
        (days_ago(n), [("Run", "Morning Run", "06:30", 32 + n % 3 * 7)], (1640 + n * 23, 118))
        for n in range(first, last - 1, -1)
    ]


def history(first: int, last: int) -> list:
    """Older invented training and food for the trend cards, `first` to `last` days ago.

    About three sessions a week (Mon and Fri runs, a Wednesday lift, a long run every other
    Saturday), slowly getting longer; food on most days, with every ninth day not logged.
    """
    days = []
    for n in range(first, last - 1, -1):
        day = days_ago(n)
        longer = (first - n) // 20  # a few minutes more every three weeks or so
        activities = []
        if day.weekday() in (0, 4):
            activities.append(("Run", "Morning Run", "06:30", 28 + n % 4 * 4 + longer))
        if day.weekday() == 2:
            activities.append(("WeightTraining", "Upper Body", "17:10", 50 + n % 3 * 5 + longer))
        if day.weekday() == 5 and n % 14 < 7:
            activities.append(("Run", "Long Run", "07:00", 66 + n % 5 * 4 + longer))
        food = None if n % 9 == 0 else (1690 + n * 37 % 380, 104 + n % 29)
        days.append((day, activities, food))
    return days


SCENARIOS = {
    # Mon run, Tue strength over budget, Wed recovery, Thu, Fri, Sat with three
    # activities and 654 kcal / 21 g so far, Sun ahead (UI_SPEC.md 11 "midweek").
    # Older history (from May to Oct 5) feeds the trends; Oct 6 and 7 stay empty, so it
    # never joins the current streak.
    "midweek": {
        "pipeline": HEALTHY,
        "nickname": "Rob",
        "target": TARGET,
        "recovery": [days_ago(3)],
        "days": history(165, 12)
        + steady_week(9, 6)
        # Last week's lifting, on a day that already counts, so the streak is unchanged.
        + [(days_ago(8), [("WeightTraining", "Upper Body", "17:10", 58)], None)]
        + [
            (days_ago(5), [("Run", "Morning Run", "06:30", 41)], (1702, 126)),
            (days_ago(4), [("WeightTraining", "Upper Body", "17:10", 64)], (2173, 141)),
            (days_ago(2), [("Run", "Tempo Run", "06:15", 38)], (1689, 122)),
            (days_ago(1), [("Run", "Easy Run", "18:40", 29)], (1755, 131)),
            (
                TODAY,
                [
                    ("Walk", "Morning Walk", "07:10", 45),
                    ("WeightTraining", "Full Body", "10:30", 68),
                    ("Run", "Afternoon Run", "13:05", 32),
                ],
                (654, 21),
            ),
        ],
    },
    # Yesterday (Fri) has nothing; today has nothing yet (UI_SPEC.md 11 "at_risk").
    "at_risk": {
        "pipeline": STALE,
        "nickname": "Rob",
        "target": TARGET,
        "recovery": [],
        "days": steady_week(9, 2),
    },
    # No targets and nothing this week; an older three-day streak (UI_SPEC.md 11 "edge_empty").
    "edge_empty": {
        "pipeline": None,
        "nickname": None,
        "target": None,
        "recovery": [],
        "days": steady_week(27, 25),
    },
}


# The seed's queries live in db/sql/demo/ (SQL in .sql files, as everywhere else).
SQL_DIR = Path("/db/sql/demo")


def sql(name: str) -> TextClause:
    return text((SQL_DIR / f"{name}.sql").read_text())


def date_key(day: date) -> int:
    return day.year * 10000 + day.month * 100 + day.day


def recreate_database(url) -> None:
    if not url.database.endswith("_demo"):
        sys.exit(f"Refusing to touch database {url.database!r}: the name must end in _demo.")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sql("recreate_drop"))
        conn.execute(sql("recreate_create"))
    admin.dispose()

    config = Config("/db/alembic.ini")
    config.set_main_option(
        "sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%")
    )
    command.upgrade(config, "head")


def insert_scenario(engine, scenario: dict) -> None:
    with engine.begin() as conn:
        for sport, app_type, label in SPORTS:
            conn.execute(
                sql("insert_activity_type"), {"sport": sport, "app_type": app_type, "label": label}
            )
        conn.execute(sql("set_nickname"), {"nickname": scenario["nickname"]})
        if scenario["target"]:
            conn.execute(sql("insert_target"), scenario["target"])
            conn.execute(sql("insert_weight_goal"), {"goal_kg": 73.0})
            insert_weights(conn, 165, 0)
        for day in scenario["recovery"]:
            conn.execute(sql("insert_recovery"), {"day": day})

        if scenario["pipeline"]:
            insert_pipeline(conn, scenario["pipeline"])

        strava_id = 1000
        for day, activities, food in scenario["days"]:
            for sport, title, start, minutes in activities:
                strava_id += 1
                insert_activity(conn, strava_id, day, sport, title, start, minutes)
                if title == "Full Body":
                    insert_exercises(conn, strava_id, FULL_BODY)
                if title == "Upper Body" and day < days_ago(5):  # history: sets as described
                    insert_exercises(conn, strava_id, upper_body(day))
            if food:
                insert_food(conn, day, *food)


def distance_m(sport: str, minutes: int) -> int | None:
    """Invented distances at a steady pace: runs 5:40 /km, walks 12:00 /km."""
    seconds_per_km = {"Run": 340, "Walk": 720}.get(sport)
    return None if seconds_per_km is None else round(minutes * 60 / seconds_per_km * 1000)


def insert_activity(conn, strava_id, day, sport, title, start, minutes) -> None:
    payload = json.dumps({"id": strava_id, "name": title})
    conn.execute(sql("insert_raw_activity"), {"id": strava_id, "payload": payload})
    conn.execute(
        sql("insert_activity"),
        {
            "id": strava_id,
            "date_key": date_key(day),
            "title": title,
            "started": f"{day}T{start}:00+08:00",
            "local": f"{day} {start}",
            "seconds": minutes * 60,
            "distance": distance_m(sport, minutes),
            "sport": sport,
        },
    )


def insert_exercises(conn, strava_id: int, exercises: list) -> None:
    for order, exercise in enumerate(exercises, start=1):
        exercise_key = conn.execute(
            sql("insert_exercise"),
            {
                "name": exercise["name"],
                "equipment": exercise["equipment"],
                "muscle_group": exercise["muscle"],
            },
        ).scalar_one()
        for number, (kind, weight, unit, reps, seconds) in enumerate(exercise["sets"], start=1):
            is_weight = kind == "weight_reps"
            conn.execute(
                sql("insert_set"),
                {
                    "exercise_key": exercise_key,
                    "exercise_order": order,
                    "set_number": number,
                    "set_kind": kind,
                    # Stored in kg; the original value and unit are kept, as in the real data.
                    "weight_kg": weight * 0.45359237 if is_weight and unit == "lb" else weight,
                    "reps": reps,
                    "distance_m": None,
                    "duration_s": seconds,
                    "orig_weight": weight if is_weight else None,
                    "orig_unit": unit if is_weight else None,
                    "note": exercise["note"],
                    "strava_id": strava_id,
                },
            )


def hours_before_now(hours: float) -> str:
    return (datetime.fromisoformat(NOW) - timedelta(hours=hours)).isoformat()


def insert_pipeline(conn, pipeline: dict) -> None:
    for source, hours, status, error in pipeline["runs"]:
        conn.execute(
            sql("insert_run"),
            {"source": source, "at": hours_before_now(hours), "status": status, "error": error},
        )
    dq_at = hours_before_now(0.5)
    run_id = conn.execute(
        sql("insert_run"), {"source": "dq", "at": dq_at, "status": "success", "error": None}
    ).scalar_one()
    for check in DQ_CHECKS:
        conn.execute(
            sql("insert_dq_result"),
            {
                "run_id": run_id,
                "check_name": check,
                "status": pipeline["dq"].get(check, "pass"),
                "observed_value": 0,
                "threshold": "demo",
                "at": dq_at,
            },
        )
    for index, (raw, line_no) in enumerate(pipeline["quarantine"]):
        conn.execute(
            sql("insert_quarantine"),
            {
                "entity_id": str(9000 + index),
                "line_no": line_no,
                "raw_content": raw,
                "at": hours_before_now(3 + index),
            },
        )


def weight_kg(n: int) -> float:
    """Invented weights: a slow fall from about 77.5 kg in May to 74.8 kg, with small wobbles."""
    return round(77.5 - (165 - n) * 0.0165 + (n % 4 - 1.5) * 0.3, 1)


def insert_weights(conn, first: int, last: int) -> None:
    """One weigh-in on most days from `first` to `last` days ago (one a day, like MyNetDiary)."""
    for n in range(first, last - 1, -1):
        if n % 6 == 0:
            continue  # no weigh-in that day
        day = days_ago(n)
        batch_id = conn.execute(sql("insert_batch"), {"day": day}).scalar_one()
        conn.execute(
            sql("insert_body_mass"),
            {
                "day": day,
                "date_key": date_key(day),
                "kg": weight_kg(n),
                "start": f"{day}T07:00:00+08:00",
                "batch_id": batch_id,
            },
        )


def insert_food(conn, day, kcal, protein) -> None:
    batch_id = conn.execute(sql("insert_batch"), {"day": day}).scalar_one()
    for idx, (sample_type, value) in enumerate([("energy", kcal), ("protein", protein)]):
        conn.execute(
            sql("insert_sample"),
            {
                "batch_id": batch_id,
                "idx": idx,
                "date_key": date_key(day),
                "day": day,
                "type": sample_type,
                "value": value,
                "start": f"{day}T12:00:00+08:00",
            },
        )


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "midweek"
    if name not in SCENARIOS:
        sys.exit(f"Unknown scenario {name!r}. Choose one of: {', '.join(SCENARIOS)}.")
    url = make_url(os.environ["WAREHOUSE_URL"])
    recreate_database(url)
    engine = create_engine(url)
    insert_scenario(engine, SCENARIOS[name])
    engine.dispose()
    print(f"Demo scenario {name!r} loaded into {url.database}.")


if __name__ == "__main__":
    main()
