"""A demo visitor's own settings, for their requests only, never saved (DECISIONS D122).

The Me page on the demo keeps what the visitor changes in their browser tab and sends it
with every request, as JSON in the X-Demo-Settings header. Here, on the demo service only:
1. the header is parsed and each value clamped to the same limits the real Me page has;
2. it is held for this one request (a ContextVar: each request has its own);
3. whenever that request's database work begins a transaction, the values are set with
   set_config(..., true), which lasts until that transaction ends. The settings lookups
   (app.target_on and friends, migration 0016) prefer them, so the streak, the calendar
   and every card use the visitor's budget for every day, at read time.
Nothing is written: the demo's database role can only read. Nothing is kept on the
server: the next request, from anyone, starts with no settings.
"""

import json
from contextvars import ContextVar
from typing import Literal

from fastapi import FastAPI, Request
from pydantic import BaseModel, ValidationError, ValidationInfo, field_validator
from sqlalchemy import Connection, Engine, event

from app.db import SQL_DIR
from app.errors import ApiError, handle_api_error

HEADER = "x-demo-settings"
MAX_HEADER_BYTES = 512

# Same limits as the real Me page (app/me.py, UI_SPEC.md 6.3); out-of-range numbers are
# moved to the nearest limit rather than refused, so a slider can't break the demo.
LIMITS = {
    "calorie_budget": (800, 6000),
    "protein_goal": (0, 400),
    "weight_goal_kg": (30.0, 250.0),
}


class DemoSettings(BaseModel):
    calorie_budget: int | None = None
    protein_goal: int | None = None
    weight_goal_kg: float | None = None
    weight_unit: Literal["kg", "lb"] | None = None
    lenient_weekends: bool | None = None
    nickname: str | None = None

    @field_validator("calorie_budget", "protein_goal", "weight_goal_kg")
    @classmethod
    def clamp(cls, value: float | None, info: ValidationInfo) -> float | None:
        if value is None:
            return None
        low, high = LIMITS[info.field_name]
        return min(max(value, low), high)

    @field_validator("nickname")
    @classmethod
    def short_name(cls, value: str | None) -> str | None:
        value = (value or "").strip()[:40]
        return value or None


# This request's settings; None outside a demo request (and always on the real app).
current: ContextVar[DemoSettings | None] = ContextVar("demo_settings", default=None)


def parse_header(raw: str | None) -> DemoSettings | None:
    if not raw:
        return None
    if len(raw.encode()) > MAX_HEADER_BYTES:
        raise ApiError(413, "payload_too_large", "Demo settings are too large.")
    try:
        return DemoSettings.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError):
        raise ApiError(422, "invalid_payload", "Demo settings are not valid.") from None


def as_parameters(settings: DemoSettings) -> dict[str, str]:
    """Every setting as text for set_config; '' for one the visitor did not change."""
    values = settings.model_dump()
    return {
        name: "" if value is None else str(value).lower() if isinstance(value, bool) else str(value)
        for name, value in values.items()
    }


APPLY_SQL = (SQL_DIR / "demo/apply_settings.sql").read_text()


def apply_to_transaction(conn: Connection) -> None:
    """SQLAlchemy's "begin" event: runs as each transaction starts, on every engine in
    this process. A no-op unless this request carries demo settings."""
    settings = current.get()
    if settings is None:
        return
    # Straight on the driver connection: a statement through `conn` here would itself
    # try to begin a transaction from inside the begin event.
    conn.connection.driver_connection.execute(APPLY_SQL, as_parameters(settings))


def add_demo_settings(app: FastAPI) -> None:
    """The demo app only (app/main.py): read each request's settings, hold them for that
    request, and apply them to its transactions."""
    if not event.contains(Engine, "begin", apply_to_transaction):
        event.listen(Engine, "begin", apply_to_transaction)

    @app.middleware("http")
    async def demo_settings(request: Request, call_next):
        try:
            settings = parse_header(request.headers.get(HEADER))
        except ApiError as error:
            return await handle_api_error(request, error)
        token = current.set(settings)
        try:
            return await call_next(request)
        finally:
            current.reset(token)  # gone before the next request, whoever sends it
