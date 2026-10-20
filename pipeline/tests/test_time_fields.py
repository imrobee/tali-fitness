"""Strava's start_date_local is local wall-clock time despite its trailing "Z" (DECISIONS D3)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from strava_fakes import SAMPLE

from include.strava.time_fields import iana_timezone, local_date, local_start, utc_start


def test_recorded_sample_local_start_is_naive_wall_clock_time():
    # Sample: start_date 2026-10-19T08:39:24Z, start_date_local 2026-10-19T16:39:24Z
    assert local_start(SAMPLE) == datetime(2026, 10, 19, 16, 39, 24)
    assert local_start(SAMPLE).tzinfo is None
    assert local_date(SAMPLE) == date(2026, 10, 19)


def test_local_start_matches_utc_start_converted_to_the_activity_time_zone():
    converted = utc_start(SAMPLE).astimezone(ZoneInfo(iana_timezone(SAMPLE)))

    assert converted.replace(tzinfo=None) == local_start(SAMPLE)


def test_late_evening_workout_stays_on_its_own_day():
    # 23:30 in Manila is 15:30 UTC. Reading the local value as UTC and converting it
    # to Manila would give 07:30 the next morning: the bug this function prevents.
    activity = {
        "start_date": "2026-10-19T15:30:00Z",
        "start_date_local": "2026-10-19T23:30:00Z",
        "timezone": "(GMT+08:00) Asia/Manila",
    }

    assert local_date(activity) == date(2026, 10, 19)
    wrong = datetime.fromisoformat(activity["start_date_local"]).astimezone(ZoneInfo("Asia/Manila"))
    assert wrong.date() == date(2026, 10, 20)


def test_utc_start_is_timezone_aware():
    assert utc_start(SAMPLE) == datetime(2026, 10, 19, 8, 39, 24, tzinfo=UTC)


def test_iana_timezone_is_read_from_the_strava_label():
    assert iana_timezone(SAMPLE) == "Asia/Manila"
