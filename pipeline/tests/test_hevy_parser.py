"""Hevy parser: golden tests on real samples, plus one test per grammar rule."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from include.parsers.hevy import KG_PER_LB, parse_hevy

SAMPLES = Path("/opt/airflow/samples")


def read(name: str) -> str:
    return (SAMPLES / name).read_text()


def volume(workout) -> Decimal:
    return sum(
        (
            s.weight_kg * s.reps
            for e in workout.exercises
            for s in e.sets
            if s.kind == "weight_reps"
        ),
        Decimal(0),
    )


def all_sets(workout):
    return [s for e in workout.exercises for s in e.sets]


# --- golden tests (ARCHITECTURE.md section 7) ----------------------------------------------


def test_golden_01_nine_exercises_22_sets_3490_90_kg():
    workout = parse_hevy(read("hevy_description_01.txt"))

    assert workout.status == "ok"
    assert len(workout.exercises) == 9
    assert len(all_sets(workout)) == 22
    assert {s.kind for s in all_sets(workout)} == {"weight_reps"}
    assert round(volume(workout), 2) == Decimal("3490.90")
    assert volume(workout) == Decimal("3490.8973504")


def test_golden_01_per_exercise_volumes_and_pounds():
    workout = parse_hevy(read("hevy_description_01.txt"))
    by_name = {
        e.name: sum((s.weight_kg * s.reps for s in e.sets), Decimal(0)) for e in workout.exercises
    }

    assert by_name["Incline Bench Press"] == 580
    assert by_name["Standing Calf Raise"] == Decimal("653.1730128")  # 40 lb
    assert by_name["Preacher Curl"] == Decimal("217.7243376")  # 20 lb
    calf = next(e for e in workout.exercises if e.name == "Standing Calf Raise")
    assert (calf.sets[0].orig_weight, calf.sets[0].orig_unit) == (40, "lb")
    assert calf.sets[0].weight_kg == 40 * KG_PER_LB


def test_golden_01_equipment_is_split_from_the_name():
    workout = parse_hevy(read("hevy_description_01.txt"))
    pairs = [(e.name, e.equipment) for e in workout.exercises]

    assert pairs[0] == ("Incline Bench Press", "Dumbbell")
    assert ("Goblet Squat", None) in pairs


def test_real_strava_description_parses_like_the_golden_file():
    # The real Strava text has blank lines and trailing spaces; the .txt sample does not.
    description = json.loads(read("strava_activity_detail_01.json"))["description"]

    workout = parse_hevy(description)

    assert workout.status == "ok"
    assert len(all_sets(workout)) == 22
    assert round(volume(workout), 2) == Decimal("3490.90")


def test_golden_02_mixed_set_kinds_and_notes():
    workout = parse_hevy(read("hevy_description_02.txt"))
    sets = all_sets(workout)

    assert workout.status == "ok"
    assert [e.name for e in workout.exercises] == [
        "Pull Up",
        "Push Up",
        "Cycling",
        "Plank",
        "Plank",
        "Cycling",
    ]
    assert len(sets) == 12
    assert [e.note for e in workout.exercises if e.note] == [
        "Training for tour de france",
        "Planking all my life",
    ]
    assert sum(s.reps for s in sets if s.kind == "reps") == 55
    assert sum(s.distance_m for s in sets if s.kind == "distance_duration") == 52_000
    assert sum(s.duration_s for s in sets if s.duration_s) == 8_642
    assert volume(workout) == 0


# --- one test per rule ---------------------------------------------------------------------


def hevy(*lines: str) -> str:
    return "\n".join(["Logged with hevyapp.com", "", *lines])


def test_without_the_marker_it_is_not_hevy_and_not_an_error():
    workout = parse_hevy("Morning run, felt great")

    assert workout.status == "not_hevy"
    assert workout.problems == []


@pytest.mark.parametrize("description", [None, "", "   \n  "])
def test_empty_descriptions_are_not_hevy(description):
    assert parse_hevy(description).status == "not_hevy"


def test_marker_must_be_the_first_line():
    assert parse_hevy("My notes\nLogged with hevyapp.com\nSquat\nSet 1: 20 kg x 5").status == (
        "not_hevy"
    )


@pytest.mark.parametrize(
    ("line", "kind", "expected"),
    [
        ("Set 1: 22.5 kg x 8", "weight_reps", {"weight_kg": Decimal("22.5"), "reps": 8}),
        ("Set 1: 40 LBS x 12", "weight_reps", {"orig_unit": "lb", "reps": 12}),
        ("Set 1: 45 lb x 5", "weight_reps", {"orig_unit": "lb", "orig_weight": 45}),
        ("Set 1: 10 reps", "reps", {"reps": 10}),
        ("Set 1: 5km - 10min", "distance_duration", {"distance_m": 5000, "duration_s": 600}),
        ("Set 1: 21km - 1h 0min", "distance_duration", {"duration_s": 3600}),
        ("Set 1: 31s", "duration", {"duration_s": 31}),
        ("Set 1: 1min 30s", "duration", {"duration_s": 90}),
        ("Set 1: 1h", "duration", {"duration_s": 3600}),
    ],
)
def test_each_set_format(line, kind, expected):
    workout = parse_hevy(hevy("Exercise", line))
    parsed = all_sets(workout)[0]

    assert workout.status == "ok"
    assert parsed.kind == kind
    for field_name, value in expected.items():
        assert getattr(parsed, field_name) == value


def test_trailing_spaces_and_missing_final_newline_are_fine():
    workout = parse_hevy("Logged with hevyapp.com\nSquat   \nSet 1: 20 kg x 5   ")

    assert workout.status == "ok"
    assert len(all_sets(workout)) == 1


@pytest.mark.parametrize(
    "line",
    [
        "Set 1: heavy",  # garbage
        "Set 1: 5.5km - 10min",  # decimal distance: not seen in real data yet
        "Set 1: 3mi - 30min",  # miles: not seen in real data yet
        "Set 1: 20 kg x",  # truncated
    ],
)
def test_unknown_set_lines_are_quarantined_never_dropped(line):
    workout = parse_hevy(hevy("Squat", "Set 1: 20 kg x 5", line))

    assert workout.status == "partial"
    assert [(p.raw_content, p.reason_code) for p in workout.problems] == [(line, "unparsed_line")]
    assert workout.problems[0].line_no == 5
    assert len(all_sets(workout)) == 1  # the good set is still kept


def test_a_repeated_set_number_is_quarantined():
    workout = parse_hevy(hevy("Squat", "Set 1: 20 kg x 5", "Set 1: 25 kg x 5"))

    assert workout.status == "partial"
    assert workout.problems[0].reason_code == "unparsed_line"


def test_a_set_before_any_exercise_is_quarantined():
    workout = parse_hevy(hevy("Set 1: 20 kg x 5", "Squat", "Set 1: 20 kg x 5"))

    assert workout.problems[0].reason_code == "unparsed_line"
    assert len(all_sets(workout)) == 1


def test_an_exercise_without_sets_is_quarantined_and_not_loaded():
    workout = parse_hevy(hevy("Squat", "Bench Press (Barbell)", "Set 1: 40 kg x 5"))

    assert workout.status == "partial"
    assert [(p.raw_content, p.reason_code) for p in workout.problems] == [
        ("Squat", "empty_exercise")
    ]
    assert [(e.order, e.name) for e in workout.exercises] == [(1, "Bench Press")]


def test_a_quoted_line_after_sets_is_not_a_note():
    workout = parse_hevy(hevy("Squat", "Set 1: 20 kg x 5", '"late note"'))

    assert workout.exercises[0].note is None
    assert workout.problems[0].reason_code == "unparsed_line"


def test_the_same_exercise_twice_gets_two_entries_in_order():
    workout = parse_hevy(
        hevy("Plank", "Set 1: 31s", "Squat", "Set 1: 20 kg x 5", "Plank", "Set 1: 1min 30s")
    )

    assert [(e.order, e.name) for e in workout.exercises] == [
        (1, "Plank"),
        (2, "Squat"),
        (3, "Plank"),
    ]
