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
from datetime import date, timedelta
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


SCENARIOS = {
    # Mon run, Tue strength over budget, Wed recovery, Thu, Fri, Sat with three
    # activities and 654 kcal / 21 g so far, Sun ahead (UI_SPEC.md 11 "midweek").
    "midweek": {
        "nickname": "Rob",
        "target": TARGET,
        "recovery": [days_ago(3)],
        "days": steady_week(9, 6)
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
        "nickname": "Rob",
        "target": TARGET,
        "recovery": [],
        "days": steady_week(9, 2),
    },
    # No targets and nothing this week; an older three-day streak (UI_SPEC.md 11 "edge_empty").
    "edge_empty": {
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
        for day in scenario["recovery"]:
            conn.execute(sql("insert_recovery"), {"day": day})

        strava_id = 1000
        for day, activities, food in scenario["days"]:
            for sport, title, start, minutes in activities:
                strava_id += 1
                insert_activity(conn, strava_id, day, sport, title, start, minutes)
            if food:
                insert_food(conn, day, *food)


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
            "sport": sport,
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
