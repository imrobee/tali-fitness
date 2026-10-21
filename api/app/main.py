"""FastAPI application: routes and the shared error format."""

from fastapi import APIRouter, FastAPI

from app.errors import ApiError, handle_api_error
from app.ingest.router import router as ingest_router

app = FastAPI(title="fitness-tracker API")
app.add_exception_handler(ApiError, handle_api_error)

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
