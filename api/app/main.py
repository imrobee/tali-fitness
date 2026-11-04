"""FastAPI application: routes and the shared error format.

Built by create_app(), an application factory: Uvicorn calls it at startup
(`uvicorn app.main:create_app --factory`), so the startup guards run before the server
accepts a request, and tests build an app from their own settings.
"""

import logging

import httpx2
from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app import (
    activities,
    activity_calendar,
    me,
    pipeline,
    progress,
    recovery,
    signin,
    sync,
    trends,
    weight,
)
from app.config import LOGIN_STATE_MINUTES, Settings, check_startup, load_settings
from app.dashboard.router import router as dashboard_router
from app.errors import ApiError, handle_api_error
from app.ingest.router import router as ingest_router
from app.logs import install_log_redaction
from app.security import add_hardening

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
    """Liveness check. No sign-in and no database access, by design."""
    return {"status": "ok"}


def add_sign_in(app: FastAPI, settings: Settings, google_transport) -> None:
    """The /auth routes for this AUTH_MODE (docs/AUTH_SPEC.md section 5)."""
    if settings.auth_mode == "google":
        app.state.google = signin.google_client(settings, google_transport)
        # The login-state cookie: Authlib keeps the state, nonce and PKCE verifier in
        # request.session, which this middleware signs (not encrypts) with
        # OAUTH_STATE_SECRET. HttpOnly always; sent to /auth only; gone after 10 minutes.
        app.add_middleware(
            SessionMiddleware,
            secret_key=settings.oauth_state_secret.get_secret_value(),
            session_cookie="login_state",
            max_age=LOGIN_STATE_MINUTES * 60,
            path="/auth",
            same_site="lax",
            https_only=settings.cookie_secure,
        )
        app.include_router(signin.google_router)
    elif settings.app_env == "dev":
        # The startup guards allow key mode only in dev; the route does not exist otherwise.
        app.include_router(signin.dev_router)
    app.include_router(signin.router)


def create_app(
    settings: Settings | None = None, google_transport: httpx2.AsyncBaseTransport | None = None
) -> FastAPI:
    """Check the configuration, then build the app. A bad config raises ConfigError.

    google_transport is for tests only: a fake Google, so no test calls the real one."""
    if settings is None:
        settings = load_settings()
    check_startup(settings)
    install_log_redaction()
    if settings.public_base_url.startswith("http://"):
        # Allowed on this Mac and the LAN in dev; production is HTTPS only (the guards).
        logger.warning("Plain HTTP: the Shortcut's ingest token travels unencrypted.")

    # No /docs, /redoc or /openapi.json in production: openapi_url=None turns off all three.
    production = settings.app_env == "production"
    app = FastAPI(title="fitness-tracker API", openapi_url=None if production else "/openapi.json")
    # Routes read the settings through the get_settings dependency, not os.environ.
    app.state.settings = settings
    app.add_exception_handler(ApiError, handle_api_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)

    add_hardening(app, settings)
    add_sign_in(app, settings, google_transport)
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
