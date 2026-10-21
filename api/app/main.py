"""FastAPI application: routes and the shared error format."""

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import me, recovery
from app.dashboard.router import router as dashboard_router
from app.errors import ApiError, handle_api_error
from app.ingest.router import router as ingest_router

app = FastAPI(title="fitness-tracker API")
app.add_exception_handler(ApiError, handle_api_error)


async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    """Bad query parameters or JSON bodies use the same error shape as everything else."""
    first = error.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_payload", "message": f"{where}: {first['msg']}"}},
    )


app.add_exception_handler(RequestValidationError, handle_validation_error)

# Why a router with a prefix: every endpoint lives under /api/v1 (ARCHITECTURE.md
# section 11), so the web dev server can forward /api/* here unchanged, and a
# future /api/v2 could sit beside it.
router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check. No API key and no database access, by design."""
    return {"status": "ok"}


app.include_router(router)
app.include_router(ingest_router)
app.include_router(dashboard_router)
app.include_router(me.router)
app.include_router(recovery.router)
