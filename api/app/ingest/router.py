"""POST /api/v1/ingest/health: the iOS Shortcut pushes Apple Health samples here."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import Engine
from starlette.concurrency import run_in_threadpool

from app import clock
from app.auth import require_ingest_token
from app.db import get_engine
from app.errors import ApiError
from app.ingest.models import IngestResponse
from app.ingest.service import ingest_body

MAX_BODY_BYTES = 1_000_000

# The Shortcut's bearer token, and nothing else, opens this router (AUTH_SPEC.md section 7).
router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_ingest_token)])


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

    # Parsing, checks and database calls block, so they run in a worker thread instead
    # of stalling the server's event loop.
    result = await run_in_threadpool(ingest_body, engine, body, started_at, clock.today())

    response.status_code = 200 if result.duplicate else 201
    return IngestResponse(
        batch_id=result.batch_id,
        received=result.received,
        accepted=result.accepted,
        rejected=result.rejected,
        duplicate=result.duplicate,
    )
