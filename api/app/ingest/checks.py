"""Validation rules for a health batch (ARCHITECTURE.md 6.2). Pure functions, no database.

Window problems reject the whole request. Sample problems reject only that sample,
which goes to ops.quarantine with a reason code while the rest of the batch is accepted.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from app.ingest.models import SampleIn, Window

ALLOWED_UNITS = {
    "dietary_energy": {"kcal", "kJ"},
    "dietary_protein": {"g"},
    "body_mass": {"kg"},
}
KCAL_PER_KJ = 0.239006
MAX_WINDOW_DAYS = 7


@dataclass(frozen=True)
class Accepted:
    idx: int
    type: str
    value: float  # as received; kJ is converted to kcal later, in core
    unit: str
    start: datetime
    local_date: date
    source: str | None


@dataclass(frozen=True)
class Rejected:
    idx: int
    reason_code: str
    error: str
    raw: dict


def device_timezone(name: str) -> ZoneInfo | None:
    """The batch's IANA time zone, or None if the name is unknown."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def window_problem(window: Window, today: date) -> tuple[str, str] | None:
    """(error code, message) if the window itself is unacceptable, else None."""
    if window.end < window.start:
        return "invalid_payload", "window.to is before window.from."
    if (window.end - window.start).days + 1 > MAX_WINDOW_DAYS:
        return "date_out_of_range", f"The window spans more than {MAX_WINDOW_DAYS} days."
    if window.end > today + timedelta(days=1):
        return "date_out_of_range", "The window ends after tomorrow."
    return None


def in_range(sample_type: str, value: float, unit: str) -> bool:
    if sample_type == "dietary_energy":
        kcal = value * KCAL_PER_KJ if unit == "kJ" else value
        return 0 < kcal <= 5000
    if sample_type == "dietary_protein":
        return 0 <= value <= 500
    return 30 <= value <= 250  # body_mass, kg


def check_sample(idx: int, raw: dict, window: Window, device_tz: ZoneInfo) -> Accepted | Rejected:
    try:
        sample = SampleIn.model_validate(raw)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        return Rejected(idx, "invalid_sample", f"{where}: {first['msg']}", raw)

    if sample.type not in ALLOWED_UNITS:
        return Rejected(idx, "unknown_type", f"Unknown type {sample.type!r}.", raw)

    if sample.unit not in ALLOWED_UNITS[sample.type]:
        message = f"Unit {sample.unit!r} not allowed for {sample.type}."
        return Rejected(idx, "bad_unit", message, raw)

    try:
        start = datetime.fromisoformat(sample.start)
    except ValueError:
        return Rejected(idx, "bad_timestamp", f"Not an ISO 8601 time: {sample.start!r}.", raw)
    if start.tzinfo is None:
        start = start.replace(tzinfo=device_tz)  # no offset: the phone's time zone

    # The day comes from the sample's own offset, computed once here (section 4).
    local_date = start.date()
    if not window.start <= local_date <= window.end:
        return Rejected(idx, "outside_window", f"{local_date} is outside the window.", raw)

    if not in_range(sample.type, sample.value, sample.unit):
        return Rejected(idx, "out_of_range", f"{sample.value} {sample.unit} is out of range.", raw)

    return Accepted(idx, sample.type, sample.value, sample.unit, start, local_date, sample.source)
