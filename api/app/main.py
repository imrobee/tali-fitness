"""FastAPI application. Slice 1 has only the liveness endpoint."""

from fastapi import APIRouter, FastAPI

app = FastAPI(title="fitness-tracker API")

# Why a router with a prefix: every endpoint lives under /api/v1 (ARCHITECTURE.md
# section 11), so the web dev server can forward /api/* here unchanged, and a
# future /api/v2 could sit beside it.
router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check. No API key and no database access, by design."""
    return {"status": "ok"}


app.include_router(router)
