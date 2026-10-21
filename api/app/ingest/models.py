"""Request and response shapes for POST /api/v1/ingest/health (ARCHITECTURE.md 6.2)."""

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Window(BaseModel):
    # "from" is a Python keyword, so the fields are named start/end and read from the
    # JSON keys "from"/"to" through aliases.
    model_config = ConfigDict(populate_by_name=True)

    start: date = Field(alias="from")
    end: date = Field(alias="to")


class HealthBatchIn(BaseModel):
    """The envelope. If this is wrong, the whole request is rejected (422)."""

    window: Window
    device_tz: str
    # Samples stay plain dicts here: each one is checked on its own in checks.py,
    # so one bad sample is quarantined instead of rejecting the whole batch.
    samples: list[dict[str, Any]]


class SampleIn(BaseModel):
    """One sample's fields and basic types (range and unit rules are in checks.py)."""

    type: str
    value: float = Field(strict=True)  # a JSON number, never a string like "540"
    unit: str
    start: str
    source: str | None = None


class IngestResponse(BaseModel):
    batch_id: UUID
    received: int
    accepted: int
    rejected: int
    duplicate: bool
