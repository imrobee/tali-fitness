"""The streak explainer says what the SQL does (web/src/streak/explainer.json, DECISIONS D129).

Two checks. Every example row in the explainer is built into the database and run through
mart.fn_day_status and mart.fn_streak, and must give the states and streak it shows. Then
each item's claims, in the explainer's own words, are backed by a case here: change a rule
in SQL without changing the words (or the other way round), and this fails.
"""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from day_builder import TODAY, add_activity, add_calories, add_recovery, add_vacation, build
from day_builder import states as day_states
from day_builder import streak as current_streak

EXPLAINER = json.loads(Path("/opt/airflow/explainer/explainer.json").read_text())
ITEMS = {item["id"]: item for item in EXPLAINER["items"]}


@pytest.mark.parametrize("item", EXPLAINER["items"], ids=lambda item: item["id"])
def test_the_example_row_is_what_the_sql_gives(engine, item):
    example = item["example"]
    shown = example["days"]
    # A row without today in it ends yesterday: today comes after it, with nothing yet.
    sequence = shown if shown[-1] == "T" else [*shown, "T"]
    days = build(engine, " ".join(sequence))
    if "break" in example:
        first, last = example["break"]
        add_vacation(engine, days[first], days[last])

    assert day_states(engine)[: len(shown)] == example["expect"]["states"]
    assert current_streak(engine).streak == example["expect"]["streak"]


def words(item_id: str) -> str:
    return ITEMS[item_id]["body"]


# --- each item's claims, as SQL cases ------------------------------------------------------


def test_a_full_day_and_every_kept_day_adds_one(engine):
    assert "Every day that keeps your streak going adds a day to it" in words("full-day")
    build(engine, "S R S O S T")  # a rest day and a day over budget, apart

    assert current_streak(engine).streak == 5


def test_one_day_over_is_fine_even_with_a_workout(engine):
    assert "One day is fine" in words("over-budget")
    build(engine, "S O S T")  # O: over budget, with a workout

    assert current_streak(engine).streak == 3


def test_two_days_over_in_a_row_end_it(engine):
    assert "Two days over budget in a row end it" in words("over-budget")
    build(engine, "S O O S T")

    assert current_streak(engine).streak == 1


def test_a_workout_without_food_is_a_rest_day(engine):
    assert "you worked out but didn't log your food" in words("rest-days")
    build(engine, "S A R S T")  # A then R: two rest days in a row

    assert current_streak(engine).streak == 1


def test_two_rest_days_in_a_row_end_it(engine):
    assert "two rest days in a row end your streak" in words("rest-days")
    build(engine, "S R R S T")

    assert current_streak(engine).streak == 1


def test_a_recovery_day_counts_as_a_rest_day(engine):
    assert "A recovery day counts as a rest day" in words("rest-days")
    days = build(engine, "S R M S T")
    add_recovery(engine, days[2])  # the empty day, logged as recovery: R then L

    assert current_streak(engine).streak == 1


def test_a_recovery_day_on_an_empty_day_keeps_it(engine):
    assert "log a recovery day instead" in words("nothing-logged")
    days = build(engine, "S S M S T")
    add_recovery(engine, days[2])

    assert current_streak(engine).streak == 4


def test_an_empty_day_ends_it(engine):
    assert "A day with no food and no workout logged ends your streak" in words("nothing-logged")
    build(engine, "S M S S T")

    assert current_streak(engine).streak == 2


def test_a_break_changes_only_the_empty_day(engine):
    assert "During a break, only a day with nothing logged ends your streak" in words("breaks")
    kept = build(engine, "S R R O O S T")
    add_vacation(engine, kept[1], kept[4])
    assert current_streak(engine).streak == 6  # rest and over pairs: fine on a break


def test_an_empty_day_still_ends_it_on_a_break(engine):
    days = build(engine, "S S M S T")
    add_vacation(engine, days[1], days[3])

    assert current_streak(engine).streak == 1


def test_a_break_can_cover_days_that_already_passed(engine):
    assert "even for days that already passed" in words("breaks")
    days = build(engine, "S O O S T")
    assert current_streak(engine).streak == 1

    add_vacation(engine, days[1], days[2])  # set afterwards

    assert current_streak(engine).streak == 4


def test_today_never_ends_it(engine):
    assert "Today never ends your streak" in words("timing")
    build(engine, "S S S T")  # nothing logged today yet

    result = current_streak(engine)
    assert (result.streak, result.today_state) == (3, "pending")


def test_yesterday_can_still_be_fixed_today(engine):
    assert "you can still fix it today by filling in its food or workout" in words("timing")
    build(engine, "S S M T")
    yesterday = TODAY - timedelta(days=1)
    assert current_streak(engine).at_risk

    add_activity(engine, yesterday)
    add_calories(engine, yesterday)

    assert current_streak(engine).streak == 3


def test_at_midnight_yesterday_is_final(engine):
    assert "At midnight, yesterday is final" in words("timing")
    build(engine, "S S M T")

    assert current_streak(engine, today=TODAY + timedelta(days=1)).streak == 0


def test_the_targets_line_states_both_modes():
    assert "past days keep the budget they had" in EXPLAINER["targets"]["real"]
    assert "applies to every day" in EXPLAINER["targets"]["demo"]
