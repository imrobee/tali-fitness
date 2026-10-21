"""raw -> core.fact_activity and Hevy text -> core.fact_set, against a real Postgres."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from strava_fakes import make_activity

from include.core.activities import transform_activities
from include.core.sets import parse_pending
from include.parsers import hevy

SAMPLES = Path("/opt/airflow/samples")
GOLDEN_01 = (SAMPLES / "hevy_description_01.txt").read_text()
GOLDEN_02 = (SAMPLES / "hevy_description_02.txt").read_text()
FETCHED = datetime(2026, 10, 21, 5, 0, tzinfo=UTC)


def land(engine: Engine, activity: dict, fetched_at: datetime = FETCHED) -> None:
    """Put one activity into raw, the way the Strava sync does."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO raw.strava_activities (strava_id, payload, fetched_at) "
                "VALUES (:id, CAST(:payload AS jsonb), :fetched_at) "
                "ON CONFLICT (strava_id) DO UPDATE "
                "SET payload = EXCLUDED.payload, fetched_at = EXCLUDED.fetched_at"
            ),
            {"id": activity["id"], "payload": json.dumps(activity), "fetched_at": fetched_at},
        )


def run_core(engine: Engine):
    transform_activities(engine)
    return parse_pending(engine)


def scalar(engine: Engine, sql: str, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def lifting(activity_id: int, description: str, start=datetime(2026, 10, 19, 8, 39, tzinfo=UTC)):
    activity = make_activity(activity_id, start, description)
    activity["sport_type"] = "WeightTraining"
    return activity


# --- fact_activity -------------------------------------------------------------------------


def test_activity_columns_come_from_the_payload(engine):
    land(engine, lifting(1, GOLDEN_01))  # 08:39 UTC = 16:39 Manila

    run_core(engine)

    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM core.fact_activity")).one()
    assert row.strava_id == 1
    assert row.date_key == 20261019
    assert row.started_local == datetime(2026, 10, 19, 16, 39)
    assert row.tz == "Asia/Manila"
    assert row.duration_s == 4069
    assert row.parse_status == "ok"


def test_late_evening_activity_keeps_its_local_day(engine):
    # 23:30 Manila is 15:30 UTC. Treating start_date_local's "Z" as UTC would give Oct 20.
    land(engine, lifting(1, "No sets", start=datetime(2026, 10, 19, 15, 30, tzinfo=UTC)))

    run_core(engine)

    assert scalar(engine, "SELECT date_key FROM core.fact_activity") == 20261019


def test_sport_types_map_through_the_seed_and_unknown_ones_become_other(engine):
    run = make_activity(1, datetime(2026, 10, 19, 8, tzinfo=UTC), description="")
    run["sport_type"] = "Run"
    odd = make_activity(2, datetime(2026, 10, 18, 8, tzinfo=UTC), description="")
    odd["sport_type"] = "Kitesurf"
    land(engine, run)
    land(engine, odd)

    run_core(engine)

    with engine.connect() as conn:
        rows = dict(
            conn.execute(
                text(
                    "SELECT a.strava_id, t.app_type FROM core.fact_activity a "
                    "JOIN core.dim_activity_type t USING (activity_type_key)"
                )
            ).all()
        )
    assert rows == {1: "run", 2: "other"}


@pytest.mark.parametrize(
    ("description", "expected"),
    [("", "not_applicable"), (None, "not_applicable"), ("Easy 5k", "not_hevy")],
)
def test_parse_status_for_activities_without_hevy_text(engine, description, expected):
    activity = make_activity(1, datetime(2026, 10, 19, 8, tzinfo=UTC))
    activity["description"] = description
    land(engine, activity)

    run_core(engine)

    assert scalar(engine, "SELECT parse_status FROM core.fact_activity") == expected


# --- fact_set: golden tests and idempotency ------------------------------------------------


def test_golden_01_loads_22_sets_and_3490_90_kg(engine):
    land(engine, lifting(1, GOLDEN_01))

    result = run_core(engine)

    assert result.sets == 22
    assert scalar(engine, "SELECT count(*) FROM core.fact_set") == 22
    assert scalar(engine, "SELECT round(sum(volume_kg), 2) FROM core.fact_set") == Decimal(
        "3490.90"
    )
    assert scalar(engine, "SELECT count(*) FROM core.dim_exercise") == 9


def test_golden_02_loads_mixed_kinds_with_notes(engine):
    land(engine, lifting(2, GOLDEN_02))

    run_core(engine)

    with engine.connect() as conn:
        kinds = dict(
            conn.execute(
                text("SELECT set_kind, count(*) FROM core.fact_set GROUP BY set_kind")
            ).all()
        )
        notes = conn.execute(
            text(
                "SELECT DISTINCT exercise_order, exercise_note FROM core.fact_set "
                "WHERE exercise_note IS NOT NULL ORDER BY exercise_order"
            )
        ).all()
    assert kinds == {"reps": 4, "distance_duration": 4, "duration": 4}
    assert [n.exercise_note for n in notes] == [
        "Training for tour de france",
        "Planking all my life",
    ]
    assert scalar(engine, "SELECT sum(volume_kg) FROM core.fact_set") == 0
    assert scalar(engine, "SELECT sum(duration_s) FROM core.fact_set") == 8642


def test_reparsing_changes_nothing_including_exercises_without_equipment(engine):
    land(engine, lifting(1, GOLDEN_01))
    run_core(engine)

    # Force a re-parse of the same text: same sets, and no new dim_exercise rows for
    # "Goblet Squat" / "Triceps Rope Pushdown" / "Cable Core Pallof Press" (NULL equipment).
    land(engine, lifting(1, GOLDEN_01), fetched_at=datetime(2026, 10, 21, 6, 0, tzinfo=UTC))
    second = run_core(engine)

    assert second.activities == 1
    assert scalar(engine, "SELECT count(*) FROM core.fact_set") == 22
    assert scalar(engine, "SELECT count(*) FROM core.dim_exercise") == 9
    assert scalar(engine, "SELECT count(*) FROM core.dim_exercise WHERE equipment IS NULL") == 3


def test_nothing_is_reparsed_when_nothing_changed(engine):
    land(engine, lifting(1, GOLDEN_01))
    run_core(engine)

    assert run_core(engine).activities == 0


def test_an_edited_description_replaces_the_sets(engine):
    land(engine, lifting(1, GOLDEN_01))
    run_core(engine)

    land(
        engine,
        lifting(1, "Logged with hevyapp.com\nSquat\nSet 1: 100 kg x 5"),
        fetched_at=datetime(2026, 10, 21, 6, 0, tzinfo=UTC),
    )
    run_core(engine)

    assert scalar(engine, "SELECT count(*) FROM core.fact_set") == 1
    assert scalar(engine, "SELECT sum(volume_kg) FROM core.fact_set") == 500


def test_a_new_parser_version_replays_every_activity(engine, monkeypatch):
    land(engine, lifting(1, GOLDEN_01))
    run_core(engine)

    monkeypatch.setattr(hevy, "PARSER_VERSION", hevy.PARSER_VERSION + 1)
    monkeypatch.setattr("include.core.sets.PARSER_VERSION", hevy.PARSER_VERSION)

    assert run_core(engine).activities == 1


# --- quarantine and muscle groups ----------------------------------------------------------


def test_unknown_lines_are_quarantined_once_and_the_activity_is_partial(engine):
    land(engine, lifting(1, "Logged with hevyapp.com\nSquat\nSet 1: 20 kg x 5\nSet 2: heavy"))
    run_core(engine)
    land(
        engine,
        lifting(1, "Logged with hevyapp.com\nSquat\nSet 1: 20 kg x 5\nSet 2: heavy"),
        fetched_at=datetime(2026, 10, 21, 6, 0, tzinfo=UTC),
    )
    run_core(engine)  # re-parse: the problem line is not quarantined twice

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM ops.quarantine")).all()
    assert [(r.source, r.entity_id, r.line_no, r.raw_content, r.reason_code) for r in rows] == [
        ("strava", "1", 4, "Set 2: heavy", "unparsed_line")
    ]
    assert scalar(engine, "SELECT parse_status FROM core.fact_activity") == "partial"
    assert scalar(engine, "SELECT count(*) FROM core.fact_set") == 1


def test_mapped_and_unmapped_muscle_groups(engine):
    land(
        engine,
        lifting(1, "Logged with hevyapp.com\nPlank\nSet 1: 31s\nZercher Squat\nSet 1: 60 kg x 5"),
    )

    run_core(engine)

    with engine.connect() as conn:
        groups = dict(
            conn.execute(text("SELECT exercise_name, muscle_group FROM core.dim_exercise")).all()
        )
    assert groups == {"Plank": "Core", "Zercher Squat": "Unmapped"}


# --- database rules ------------------------------------------------------------------------


def test_the_database_rejects_a_set_that_breaks_its_kinds_rules(engine):
    land(engine, lifting(1, GOLDEN_01))
    run_core(engine)

    with pytest.raises(Exception, match="check constraint"), engine.begin() as conn:
        # A weight_reps set without reps.
        conn.execute(
            text(
                "INSERT INTO core.fact_set (activity_key, date_key, exercise_key, exercise_order, "
                "set_number, set_kind, weight_kg, orig_weight, orig_unit) "
                "SELECT activity_key, date_key, (SELECT min(exercise_key) FROM core.dim_exercise), "
                "99, 1, 'weight_reps', 20, 20, 'kg' FROM core.fact_activity"
            )
        )
