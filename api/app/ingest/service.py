"""One Shortcut push, from raw bytes to the warehouse: parse, check, store, apply.

The HTTP route (router.py) calls this after its size limit. The public demo's seeder
calls it too, with synthetic payloads (DECISIONS D119), so demo nutrition data goes
through exactly the checks and loads that real pushes do.
"""

from datetime import date, datetime

from pydantic import ValidationError
from sqlalchemy import Engine

from app.errors import ApiError
from app.ingest.checks import Accepted, Rejected, check_sample, device_timezone, window_problem
from app.ingest.models import HealthBatchIn
from app.ingest.store import IngestResult, store_batch


def ingest_body(engine: Engine, body: bytes, started_at: datetime, today: date) -> IngestResult:
    """Raises ApiError (422) for a payload the route would reject."""
    try:
        batch = HealthBatchIn.model_validate_json(body)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "body"
        raise ApiError(422, "invalid_payload", f"{where}: {first['msg']}") from error

    if not batch.samples:
        # An empty run means the Shortcut failed; rejecting it makes that visible.
        raise ApiError(422, "empty_batch", "The batch has no samples.")

    device_tz = device_timezone(batch.device_tz)
    if device_tz is None:
        raise ApiError(422, "invalid_payload", f"Unknown device_tz {batch.device_tz!r}.")

    problem = window_problem(batch.window, today)
    if problem is not None:
        code, message = problem
        raise ApiError(422, code, message)

    checked = [check_sample(i, raw, batch.window, device_tz) for i, raw in enumerate(batch.samples)]
    accepted = [sample for sample in checked if isinstance(sample, Accepted)]
    rejected = [sample for sample in checked if isinstance(sample, Rejected)]
    return store_batch(engine, body, batch, accepted, rejected, started_at)
