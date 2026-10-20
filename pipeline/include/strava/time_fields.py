"""Reading Strava's time fields correctly (ARCHITECTURE.md section 4, DECISIONS D3).

Strava sends two start times:
- start_date:       UTC, e.g. "2026-10-19T08:39:24Z"
- start_date_local: wall-clock time where the activity happened, e.g. "2026-10-19T16:39:24Z".
  The trailing "Z" is misleading: this value is NOT UTC. Treating it as UTC would shift
  evening workouts to the next day.
"""

from datetime import date, datetime


def utc_start(activity: dict) -> datetime:
    """Timezone-aware UTC start time."""
    return datetime.fromisoformat(activity["start_date"])


def local_start(activity: dict) -> datetime:
    """Naive local start time: start_date_local with its misleading "Z" removed."""
    return datetime.fromisoformat(activity["start_date_local"].removesuffix("Z"))


def local_date(activity: dict) -> date:
    """The calendar day the activity happened on, in its own time zone."""
    return local_start(activity).date()


def iana_timezone(activity: dict) -> str:
    """ "(GMT+08:00) Asia/Manila" -> "Asia/Manila"."""
    return activity["timezone"].split(") ", 1)[1]
