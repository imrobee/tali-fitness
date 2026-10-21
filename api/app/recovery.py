"""POST/DELETE /api/v1/recovery: log or undo a recovery day (the single freeze).

The rule lives in SQL (mart.fn_recovery_state): a day can be logged only when the
recovery card for it says 'available', so the card and the endpoint never disagree.
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import Engine

from app import clock
from app.auth import require_api_key
from app.db import get_engine, load_sql
from app.errors import ApiError

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])

# Why a day cannot be logged, by recovery-card state (copy follows UI_SPEC.md 5.4).
NOT_ALLOWED = {
    "locked": "Recovery days can only be set for today or yesterday.",
    "counted": "This day already counts: it has a workout and logged calories.",
    "no_freeze": "No freezes left: the previous day was a recovery day.",
    "blocked": "A freeze needs the previous day to be counted. Fill it in first.",
}


class RecoveryIn(BaseModel):
    date: date
    note: str | None = Field(default=None, max_length=200)


class RecoveryOut(BaseModel):
    date: date
    state: str


@router.post("/recovery", response_model=RecoveryOut)
def log_recovery(
    body: RecoveryIn, response: Response, engine: Annotated[Engine, Depends(get_engine)]
) -> RecoveryOut:
    with engine.begin() as conn:
        state = conn.execute(
            load_sql("api/recovery_state.sql"), {"today": clock.today(), "day": body.date}
        ).scalar_one()
        if state == "logged":
            response.status_code = 200  # already logged: nothing to do
            return RecoveryOut(date=body.date, state="logged")
        if state != "available":
            raise ApiError(422, "recovery_not_allowed", NOT_ALLOWED[state])
        conn.execute(load_sql("api/insert_recovery.sql"), {"day": body.date, "note": body.note})
    response.status_code = 201
    return RecoveryOut(date=body.date, state="logged")


@router.delete("/recovery/{day}", status_code=204)
def undo_recovery(day: date, engine: Annotated[Engine, Depends(get_engine)]) -> Response:
    today = clock.today()
    if day not in (today, today - timedelta(days=1)):
        raise ApiError(422, "recovery_not_allowed", NOT_ALLOWED["locked"])
    with engine.begin() as conn:
        conn.execute(load_sql("api/delete_recovery.sql"), {"day": day})
    return Response(status_code=204)
