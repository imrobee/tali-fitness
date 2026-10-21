"""The API's only source of "now" and "today" (ARCHITECTURE.md section 4).

NOW_OVERRIDE (ISO 8601) freezes the clock for fixtures and screenshots. It is honored
only when APP_ENV is dev or test, so it can never change a hosted app's dates.
"""

import os
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def app_timezone() -> ZoneInfo:
    return ZoneInfo(os.environ.get("APP_TIMEZONE", "Asia/Manila"))


def now() -> datetime:
    override = os.environ.get("NOW_OVERRIDE", "")
    if override and os.environ.get("APP_ENV") in ("dev", "test"):
        frozen = datetime.fromisoformat(override)
        if frozen.tzinfo is None:
            frozen = frozen.replace(tzinfo=app_timezone())
        return frozen
    return datetime.now(UTC)


def today() -> date:
    """Today's date in the profile time zone; the browser never decides this."""
    return now().astimezone(app_timezone()).date()
