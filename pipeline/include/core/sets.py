"""Parse Hevy descriptions and load the sets into core.fact_set (ARCHITECTURE.md 6.1, 7).

Each activity is parsed and loaded in its own transaction: delete its sets and open
quarantine rows, insert the new ones, record the status. Running it twice gives the
same result (idempotent), and a failure leaves that activity exactly as it was.
"""

from dataclasses import dataclass

from sqlalchemy import Connection, Engine

from include.db import load_sql
from include.parsers.hevy import PARSER_VERSION, ParsedWorkout, parse_hevy


@dataclass
class ParseResult:
    activities: int  # activities parsed this run
    sets: int  # sets written
    quarantined: int  # problem lines sent to ops.quarantine


def parse_status(description: str | None, workout: ParsedWorkout) -> str:
    """'not_applicable' when there is no description at all; otherwise the parser's view."""
    if not (description or "").strip():
        return "not_applicable"
    return workout.status


def exercise_key(conn: Connection, name: str, equipment: str | None) -> int:
    params = {"exercise_name": name, "equipment": equipment}
    conn.execute(load_sql("core/insert_exercise.sql"), params)
    return conn.execute(load_sql("core/get_exercise_key.sql"), params).scalar_one()


def load_activity(conn: Connection, activity, workout: ParsedWorkout) -> tuple[int, int]:
    """Replace one activity's sets and quarantine rows. Returns (sets, problems)."""
    strava_id = str(activity.strava_id)
    conn.execute(load_sql("core/delete_sets.sql"), {"activity_key": activity.activity_key})
    conn.execute(
        load_sql("ops/delete_open_quarantine.sql"), {"source": "strava", "entity_id": strava_id}
    )

    set_rows = []
    for exercise in workout.exercises:
        key = exercise_key(conn, exercise.name, exercise.equipment)
        for parsed in exercise.sets:
            set_rows.append(
                {
                    "activity_key": activity.activity_key,
                    "date_key": activity.date_key,
                    "exercise_key": key,
                    "exercise_order": exercise.order,
                    "set_number": parsed.set_number,
                    "set_kind": parsed.kind,
                    "weight_kg": parsed.weight_kg,
                    "reps": parsed.reps,
                    "distance_m": parsed.distance_m,
                    "duration_s": parsed.duration_s,
                    "orig_weight": parsed.orig_weight,
                    "orig_unit": parsed.orig_unit,
                    "exercise_note": exercise.note,
                }
            )
    if set_rows:
        conn.execute(load_sql("core/insert_set.sql"), set_rows)

    if workout.problems:
        conn.execute(
            load_sql("ops/insert_quarantine.sql"),
            [
                {
                    "source": "strava",
                    "entity_id": strava_id,
                    "line_no": problem.line_no,
                    "raw_content": problem.raw_content,
                    "reason_code": problem.reason_code,
                    "error": None,
                }
                for problem in workout.problems
            ],
        )

    conn.execute(
        load_sql("core/mark_parsed.sql"),
        {
            "activity_key": activity.activity_key,
            "parse_status": parse_status(activity.description_raw, workout),
            "parser_version": PARSER_VERSION,
        },
    )
    return len(set_rows), len(workout.problems)


def parse_pending(engine: Engine) -> ParseResult:
    """Parse every activity that is new, re-fetched, or parsed by an older grammar."""
    with engine.connect() as conn:
        pending = conn.execute(
            load_sql("core/activities_to_parse.sql"), {"parser_version": PARSER_VERSION}
        ).all()

    result = ParseResult(activities=0, sets=0, quarantined=0)
    for activity in pending:
        workout = parse_hevy(activity.description_raw)
        with engine.begin() as conn:  # one transaction per activity
            sets, problems = load_activity(conn, activity, workout)
        result.activities += 1
        result.sets += sets
        result.quarantined += problems

    with engine.begin() as conn:
        conn.execute(load_sql("core/apply_muscle_groups.sql"))
    return result
