"""raw.strava_activities -> core.fact_activity, plus the seed dimensions.

The transform is SQL (db/sql/core); Python only loads the seed CSVs and runs the
statements in order, in one transaction.
"""

import csv
from pathlib import Path

from sqlalchemy import Connection, Engine

from include.db import load_sql

# db/ is mounted read-only into the Airflow container at /opt/airflow/db.
SEEDS_DIR = Path("/opt/airflow/db/seeds")


def read_seed(name: str) -> list[dict]:
    with (SEEDS_DIR / name).open(newline="") as seed_file:
        return list(csv.DictReader(seed_file))


def load_seeds(conn: Connection) -> None:
    """Upsert the seed CSVs; editing a CSV takes effect on the next run."""
    conn.execute(load_sql("core/upsert_activity_type.sql"), read_seed("dim_activity_type.csv"))
    conn.execute(load_sql("core/upsert_exercise_muscle.sql"), read_seed("exercise_muscle_map.csv"))


def transform_activities(engine: Engine) -> int:
    """Upsert every raw activity into core.fact_activity. Returns the row count touched."""
    with engine.begin() as conn:
        load_seeds(conn)
        conn.execute(load_sql("core/add_unseen_sport_types.sql"))
        result = conn.execute(load_sql("core/upsert_fact_activity.sql"))
        return result.rowcount
