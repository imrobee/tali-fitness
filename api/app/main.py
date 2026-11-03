"""FastAPI application: routes and the shared error format.

Built by create_app(), an application factory: Uvicorn calls it at startup
(`uvicorn app.main:create_app --factory`), so the startup guards run before the server
accepts a request, and tests build an app from their own settings.
"""

import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import (
    activities,
    activity_calendar,
    me,
    pipeline,
    progress,
    recovery,
    sync,
    trends,
    weight,
)
from app.config import Settings, check_startup, load_settings
from app.dashboard.router import router as dashboard_router
from app.errors import ApiError, handle_api_error
from app.ingest.router import router as ingest_router

logger = logging.getLogger(__name__)


async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    """Bad query parameters or JSON bodies use the same error shape as everything else."""
    first = error.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_payload", "message": f"{where}: {first['msg']}"}},
    )


# Why a router with a prefix: every endpoint lives under /api/v1 (ARCHITECTURE.md
# section 11), so the web dev server can forward /api/* here unchanged, and a
# future /api/v2 could sit beside it.
router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check. No API key and no database access, by design."""
    return {"status": "ok"}


def create_app(settings: Settings | None = None) -> FastAPI:
    """Check the configuration, then build the app. A bad config raises ConfigError."""
    if settings is None:
        settings = load_settings()
    check_startup(settings)
    if settings.public_base_url.startswith("http://"):
        # Allowed on this Mac and the LAN in dev; production is HTTPS only (the guards).
        logger.warning("Plain HTTP: the Shortcut's ingest token travels unencrypted.")

    app = FastAPI(title="fitness-tracker API")
    # Routes read the settings through the get_settings dependency, not os.environ.
    app.state.settings = settings
    app.add_exception_handler(ApiError, handle_api_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)

    app.include_router(router)
    app.include_router(ingest_router)
    app.include_router(dashboard_router)
    app.include_router(me.router)
    app.include_router(recovery.router)
    app.include_router(pipeline.router)
    app.include_router(activities.router)
    app.include_router(activity_calendar.router)
    app.include_router(trends.router)
    app.include_router(weight.router)
    app.include_router(progress.router)
    app.include_router(sync.router)
    return app
