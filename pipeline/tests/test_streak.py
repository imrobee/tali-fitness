"""The streak rules in SQL: the mandatory scenarios of ARCHITECTURE.md 8.4 (Slice 7d).

Today is Wednesday 2026-10-21, so Oct 17 and 18 are the weekend before. Notation in
day_builder.py: S success, O over, Ov over without a workout, R and A rest days, L a
logged recovery day, M nothing, T/Ts/To/Tr today.
"""

from datetime import date, timedelta

import pytest
from day_builder import (
    TODAY,
    add_activity,
    add_calories,
    add_recovery,
    add_vacation,
    build,
    relax_weekends,
)
from day_builder import states as day_states
from day_builder import streak as current_streak
from sqlalchemy import text

# (scenario number, sequence, expected streak, expected at_risk)
SCENARIOS = [
    (1, "S S S T", 3, False),  # today, nothing yet, never breaks
    (2, "S S S Ts", 4, False),
    (3, "S O S T", 3, False),  # over budget once is fine
    (4, "S O O S T", 1, False),  # two over in a row break
    (5, "S R S T", 3, False),  # one rest day is fine
    (6, "S R R S T", 1, False),  # two rest days in a row break
    (7, "S A R S T", 1, False),  # a workout without food is a rest day too
    (8, "S M S S T", 2, False),  # a missed day breaks
    (9, "S S M T", 2, True),  # yesterday missed: at risk until midnight
    (10, "S S M Ts", 3, True),  # today counts on top of it
    (11, "S R R T", 2, True),  # yesterday a second rest day: at risk
    (12, "S S R Tr", 3, False),  # today a second rest day: not over yet, not counted
    (13, "S S S To", 4, False),  # over budget today after a success counts
    (14, "S O O T", 2, True),  # yesterday a second over day: at risk
    (15, "M M T", 0, False),  # nothing to protect
    (16, "S O R O R T", 5, False),  # alternating never makes a pair
    (17, "S Ov Ov S T", 1, False),  # over without a workout is still over
    (18, "S S L T", 3, False),  # a logged recovery day on a missed day: a rest day
    (19, "S R Lw S T", 1, False),  # a logged recovery day is a rest day even with a workout
    (20, "R S T", 2, False),  # a rest day on the very first day counts
]


@pytest.mark.parametrize(("number", "sequence", "expected_streak", "expected_at_risk"), SCENARIOS)
def test_scenario(engine, number, sequence, expected_streak, expected_at_risk):
    build(engine, sequence)

    result = current_streak(engine)

    assert (result.streak, result.at_risk) == (expected_streak, expected_at_risk), sequence


# --- yesterday and today -------------------------------------------------------------------


def test_filling_in_yesterday_heals_it(engine):
    build(engine, "S S M T")
    assert (current_streak(engine).streak, current_streak(engine).at_risk) == (2, True)

    yesterday = TODAY - timedelta(days=1)
    add_activity(engine, yesterday)
    add_calories(engine, yesterday)

    assert (current_streak(engine).streak, current_streak(engine).at_risk) == (3, False)


def test_logging_yesterday_as_a_recovery_day_heals_it(engine):
    build(engine, "S S M T")

    add_recovery(engine, TODAY - timedelta(days=1))

    assert (current_streak(engine).streak, current_streak(engine).at_risk) == (3, False)


def test_an_unhealed_yesterday_breaks_at_midnight(engine):
    build(engine, "S S M T")  # today Oct 21: Oct 20 is at risk

    tomorrow = TODAY + timedelta(days=1)  # Oct 22: Oct 20 is now two days back

    assert day_states(engine, today=tomorrow)[-3:] == ["broken", "at_risk", "pending"]
    assert current_streak(engine, today=tomorrow).streak == 0


def test_day_states_for_a_mixed_week(engine):
    build(engine, "S O O S M T")

    assert day_states(engine) == ["counted", "counted", "broken", "counted", "at_risk", "pending"]


def test_the_streak_says_why_today_is_pending(engine):
    build(engine, "S R Tr")

    result = current_streak(engine)

    assert (result.today_state, result.today_kind, result.yesterday_kind) == (
        "pending",
        "recovery",
        "recovery",
    )


def test_a_sample_at_23_59_counts_for_that_day(engine):
    yesterday = TODAY - timedelta(days=1)
    add_activity(engine, yesterday)
    add_calories(engine, yesterday, at="23:59")

    assert day_states(engine)[0] == "counted"


def test_no_data_at_all_means_no_streak(engine):
    result = current_streak(engine)

    assert (result.streak, result.at_risk, result.today_state) == (0, False, None)


# --- relaxed weekends ----------------------------------------------------------------------

# Thu Oct 15 to today: Fri and Sat over budget, then three good days.
OVER_ON_FRIDAY_AND_SATURDAY = "S O O S S S T"


def test_weekends_are_strict_by_default(engine):
    build(engine, OVER_ON_FRIDAY_AND_SATURDAY)

    assert current_streak(engine).streak == 3  # Saturday broke it


def test_on_a_relaxed_weekend_only_a_missed_day_breaks(engine):
    relax_weekends(engine, date(2026, 10, 1))
    build(engine, OVER_ON_FRIDAY_AND_SATURDAY)

    assert current_streak(engine).streak == 6


def test_a_relaxed_weekend_day_does_not_set_up_a_pair_for_monday(engine):
    relax_weekends(engine, date(2026, 10, 1))
    build(engine, "S S S O O S T")  # Sunday and Monday over

    assert current_streak(engine).streak == 6


def test_a_missed_saturday_still_breaks_a_relaxed_weekend(engine):
    relax_weekends(engine, date(2026, 10, 1))
    build(engine, "S S M S S S T")  # Saturday missed

    assert current_streak(engine).streak == 3


def test_relaxing_weekends_today_does_not_rewrite_last_weekend(engine):
    relax_weekends(engine, TODAY)
    build(engine, OVER_ON_FRIDAY_AND_SATURDAY)

    assert current_streak(engine).streak == 3


# --- vacation ------------------------------------------------------------------------------

# Tue Oct 13 to today, with a vacation from Wed Oct 14 to Sun Oct 18.
ON_VACATION = "S R R R Ov Ov S S T"


def test_on_vacation_rest_and_over_days_never_break(engine):
    add_vacation(engine, date(2026, 10, 14), date(2026, 10, 18))
    build(engine, ON_VACATION)

    assert current_streak(engine).streak == 8


def test_a_missed_day_breaks_even_on_vacation(engine):
    add_vacation(engine, date(2026, 10, 14), date(2026, 10, 18))
    build(engine, "S R R M Ov Ov S S T")  # Fri Oct 16 missed

    assert current_streak(engine).streak == 4


def test_a_vacation_set_afterwards_covers_past_days(engine):
    build(engine, ON_VACATION)
    assert current_streak(engine).streak == 2  # the Ov Ov pair on Sunday broke it

    add_vacation(engine, date(2026, 10, 14), date(2026, 10, 18))

    assert current_streak(engine).streak == 8


# --- the recovery card ---------------------------------------------------------------------


def recovery_state(engine, day: date) -> str:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT mart.fn_recovery_state(:today, :day)"), {"today": TODAY, "day": day}
        ).scalar_one()


YESTERDAY = TODAY - timedelta(days=1)


@pytest.mark.parametrize(
    ("sequence", "day", "expected"),
    [
        ("S S T", TODAY, "available"),  # nothing logged today yet: a rest day would help
        ("S S Ts", TODAY, "counted"),  # today already keeps the streak
        ("S R Tr", TODAY, "blocked"),  # yesterday was a rest day: a second one breaks anyway
        ("S M T", YESTERDAY, "available"),  # fill yesterday in as a rest day
        ("S L T", YESTERDAY, "logged"),
        ("S S S T", TODAY - timedelta(days=2), "locked"),  # only today or yesterday
    ],
)
def test_the_recovery_card_offers_a_rest_day_only_when_it_helps(engine, sequence, day, expected):
    build(engine, sequence)

    assert recovery_state(engine, day) == expected


def test_a_rest_day_on_vacation_is_always_offered(engine):
    add_vacation(engine, YESTERDAY, TODAY)
    build(engine, "S R T")  # a rest day yesterday would block today, but not on vacation

    assert recovery_state(engine, TODAY) == "available"
