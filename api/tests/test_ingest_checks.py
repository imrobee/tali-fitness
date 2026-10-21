"""Validation rules for health samples and windows (pure functions, no database)."""

from datetime import date
from zoneinfo import ZoneInfo

import pytest

from app.ingest.checks import Accepted, Rejected, check_sample, device_timezone, window_problem
from app.ingest.models import Window

MANILA = ZoneInfo("Asia/Manila")
WINDOW = Window(start=date(2026, 10, 19), end=date(2026, 10, 20))


def sample(**changes) -> dict:
    base = {
        "type": "dietary_energy",
        "value": 540,
        "unit": "kcal",
        "start": "2026-10-20T12:41:00+08:00",
        "source": "MyNetDiary",
    }
    return {**base, **changes}


def check(raw: dict) -> Accepted | Rejected:
    return check_sample(0, raw, WINDOW, MANILA)


def reason(raw: dict) -> str:
    result = check(raw)
    assert isinstance(result, Rejected), result
    return result.reason_code


def test_a_normal_energy_sample_is_accepted_with_its_local_date():
    result = check(sample())

    assert isinstance(result, Accepted)
    assert result.local_date == date(2026, 10, 20)
    assert result.value == 540


def test_a_sample_at_23_59_local_counts_for_that_day():
    result = check(sample(start="2026-10-19T23:59:00+08:00"))

    assert isinstance(result, Accepted)
    assert result.local_date == date(2026, 10, 19)


def test_the_day_comes_from_the_samples_own_offset_not_utc():
    # 00:30 in Manila is still the previous day in UTC; the local date must win.
    result = check(sample(start="2026-10-20T00:30:00+08:00"))

    assert result.local_date == date(2026, 10, 20)


def test_a_timestamp_without_offset_uses_the_device_time_zone():
    result = check(sample(start="2026-10-20T12:41:00"))

    assert isinstance(result, Accepted)
    assert result.start.tzinfo == MANILA


def test_protein_and_body_mass_are_accepted():
    assert isinstance(check(sample(type="dietary_protein", value=0, unit="g")), Accepted)
    assert isinstance(check(sample(type="body_mass", value=72.5747792, unit="kg")), Accepted)


def test_kilojoules_are_accepted_and_range_checked_in_kcal():
    assert isinstance(check(sample(value=2000, unit="kJ")), Accepted)  # 478 kcal
    assert reason(sample(value=25000, unit="kJ")) == "out_of_range"  # 5975 kcal


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"value": 0}, "out_of_range"),  # energy must be above 0
        ({"value": 5001}, "out_of_range"),
        ({"type": "dietary_protein", "value": 501, "unit": "g"}, "out_of_range"),
        ({"type": "body_mass", "value": 29, "unit": "kg"}, "out_of_range"),
        ({"type": "body_mass", "value": 165, "unit": "lb"}, "bad_unit"),
        ({"unit": "Cal"}, "bad_unit"),
        ({"type": "dietery_energy"}, "unknown_type"),  # the typo from the Slice 0 spike
        ({"start": "10/20/26, 11:00 AM"}, "bad_timestamp"),  # the spike's first format
        ({"start": "2026-10-21T08:00:00+08:00"}, "outside_window"),
        ({"value": "540"}, "invalid_sample"),  # a string, not a number
    ],
)
def test_bad_samples_are_rejected_with_a_reason(changes, expected):
    assert reason(sample(**changes)) == expected


def test_a_sample_missing_a_field_is_invalid():
    raw = sample()
    del raw["start"]

    assert reason(raw) == "invalid_sample"


def test_rejected_sample_keeps_its_raw_content():
    raw = sample(unit="Cal")

    assert check(raw).raw == raw


def test_window_rules():
    today = date(2026, 10, 20)
    ok = Window(start=date(2026, 10, 19), end=date(2026, 10, 21))  # ends tomorrow: allowed
    reversed_window = Window(start=date(2026, 10, 20), end=date(2026, 10, 19))
    eight_days = Window(start=date(2026, 10, 13), end=date(2026, 10, 20))
    after_tomorrow = Window(start=date(2026, 10, 20), end=date(2026, 10, 22))

    assert window_problem(ok, today) is None
    assert window_problem(reversed_window, today)[0] == "invalid_payload"
    assert window_problem(eight_days, today)[0] == "date_out_of_range"
    assert window_problem(after_tomorrow, today)[0] == "date_out_of_range"


def test_device_timezone():
    assert device_timezone("Asia/Manila") == MANILA
    assert device_timezone("Mars/Olympus") is None
