"""POST /api/v1/ingest/health: the iOS Shortcut pushes Apple Health samples here."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import ValidationError
from sqlalchemy import Engine
from starlette.concurrency import run_in_threadpool

from app import clock
from app.auth import require_api_key
from app.db import get_engine
from app.errors import ApiError
from app.ingest.checks import Accepted, Rejected, check_sample, device_timezone, window_problem
from app.ingest.models import HealthBatchIn, IngestResponse
from app.ingest.store import store_batch

MAX_BODY_BYTES = 1_000_000

# Every route on this router requires the X-API-Key header.
router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


@router.post("/ingest/health", response_model=IngestResponse)
async def ingest_health(
    request: Request, response: Response, engine: Annotated[Engine, Depends(get_engine)]
) -> IngestResponse:
    started_at = clock.now()

    # Read the raw bytes ourselves: we need them for the duplicate check (sha256)
    # and to store the payload exactly as received.
    declared_size = int(request.headers.get("content-length") or 0)
    if declared_size > MAX_BODY_BYTES:
        raise ApiError(413, "payload_too_large", "The body is larger than 1 MB.")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise ApiError(413, "payload_too_large", "The body is larger than 1 MB.")

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

    problem = window_problem(batch.window, clock.today())
    if problem is not None:
        code, message = problem
        raise ApiError(422, code, message)

    checked = [check_sample(i, raw, batch.window, device_tz) for i, raw in enumerate(batch.samples)]
    accepted = [sample for sample in checked if isinstance(sample, Accepted)]
    rejected = [sample for sample in checked if isinstance(sample, Rejected)]

    # Database calls block, so they run in a worker thread instead of stalling the
    # server's event loop.
    result = await run_in_threadpool(
        store_batch, engine, body, batch, accepted, rejected, started_at
    )

    response.status_code = 200 if result.duplicate else 201
    return IngestResponse(
        batch_id=result.batch_id,
        received=result.received,
        accepted=result.accepted,
        rejected=result.rejected,
        duplicate=result.duplicate,
    )
