"""GET /api/v1/dashboard?date=YYYY-MM-DD"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Engine

from app import clock
from app.auth import require_api_key
from app.dashboard.build import build_dashboard
from app.dashboard.models import Dashboard
from app.db import get_engine

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


# A plain `def` (not async): FastAPI runs it in a worker thread, so the blocking database
# calls do not stall the server.
@router.get("/dashboard", response_model=Dashboard)
def dashboard(
    engine: Annotated[Engine, Depends(get_engine)],
    selected: Annotated[date | None, Query(alias="date")] = None,
) -> Dashboard:
    today = clock.today()
    now_local = clock.now().astimezone(clock.app_timezone())
    with engine.connect() as conn:
        return build_dashboard(conn, today, now_local, selected or today)
