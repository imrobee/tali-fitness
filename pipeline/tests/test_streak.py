"""The streak and freeze rules in SQL: the 17 mandatory scenarios (ARCHITECTURE.md 8.4)."""

from datetime import timedelta

import pytest
from day_builder import TODAY, add_activity, add_calories, add_recovery, add_target, build
from day_builder import states as day_states
from day_builder import streak as current_streak
from sqlalchemy import text

# (scenario number, sequence, expected streak, expected at_risk)
SCENARIOS = [
    (1, "Q Q Q T", 3, False),  # today pending never breaks
    (2, "Q Q Q Tq", 4, False),
    (3, "Q R Q T", 2, False),  # R is transparent
    (4, "Q R R Q Q T", 2, False),  # second R invalid, acts as missed
    (5, "Q M Q Q T", 2, False),  # an older M breaks the chain
    (6, "Q Q M T", 2, True),  # yesterday is at_risk
    (7, "Q Q M Tq", 3, True),  # today counts on top of the pre-miss chain
    (10, "Q Q R(today)", 2, False),  # recovery today
    (11, "M M T", 0, False),  # no chain to protect
    (12, "R Q T", 1, False),  # first-day recovery is valid
    (13, "Q Rq Q T", 3, False),  # qualifying wins over recovery
    (14, "Q Qo Q T", 3, False),  # over budget never affects the streak
    (15, "Q A T", 1, True),  # activity without calories does not qualify
    (16, "Q R M Q T", 1, False),  # recovery then a miss breaks
    (17, "Q C T", 1, True),  # calories without activity does not qualify
]


@pytest.mark.parametrize(("number", "sequence", "expected_streak", "expected_at_risk"), SCENARIOS)
def test_scenario(engine, number, sequence, expected_streak, expected_at_risk):
    if "Qo" in sequence:
        add_target(engine, TODAY - timedelta(days=30), budget=2000)  # Qo eats 2500
    build(engine, sequence)

    result = current_streak(engine)

    assert (result.streak, result.at_risk) == (expected_streak, expected_at_risk), sequence


def test_scenario_8_heal_yesterday_with_a_workout_and_calories(engine):
    build(engine, "Q Q M T")
    assert (current_streak(engine).streak, current_streak(engine).at_risk) == (2, True)

    yesterday = TODAY - timedelta(days=1)
    add_activity(engine, yesterday)
    add_calories(engine, yesterday)

    assert (current_streak(engine).streak, current_streak(engine).at_risk) == (3, False)


def test_scenario_9_heal_yesterday_with_the_freeze(engine):
    build(engine, "Q Q M T")

    add_recovery(engine, TODAY - timedelta(days=1))  # the day before it was Q

    assert (current_streak(engine).streak, current_streak(engine).at_risk) == (2, False)


def test_scenario_10_using_the_freeze_today_leaves_none(engine):
    build(engine, "Q Q R(today)")

    assert current_streak(engine).freezes_left == 0


def test_an_unhealed_yesterday_becomes_missed_at_midnight(engine):
    build(engine, "Q Q M T")  # today Oct 21: Oct 20 is at risk

    tomorrow = TODAY + timedelta(days=1)  # Oct 22: Oct 20 is now two days back

    assert day_states(engine, today=tomorrow)[-3:] == ["missed", "at_risk", "today_pending"]
    assert current_streak(engine, today=tomorrow).streak == 0


def test_day_states_for_a_mixed_week(engine):
    build(engine, "Q R R Q M T")

    assert day_states(engine) == [
        "qualifying",
        "recovery",
        "missed",  # second recovery: the previous day did not qualify
        "qualifying",
        "at_risk",
        "today_pending",
    ]


def test_freezes_left_follows_the_rule(engine):
    build(engine, "Q R Q T")

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT state, freezes_left FROM mart.fn_day_status(:today)"), {"today": TODAY}
        ).all()
    assert [(r.state, r.freezes_left) for r in rows] == [
        ("qualifying", 1),
        ("recovery", 0),  # freeze in use
        ("qualifying", 1),  # released by the next qualifying day
        ("today_pending", 1),
    ]


def test_a_sample_at_23_59_counts_for_that_day(engine):
    yesterday = TODAY - timedelta(days=1)
    add_activity(engine, yesterday)
    add_calories(engine, yesterday, at="23:59")

    assert day_states(engine)[0] == "qualifying"


def test_no_data_at_all_means_no_streak(engine):
    result = current_streak(engine)

    assert (result.streak, result.at_risk, result.freezes_left) == (0, False, 1)
