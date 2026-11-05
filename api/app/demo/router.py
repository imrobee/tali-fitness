"""The demo service's /auth routes. They replace the real ones, which are not mounted in
demo mode: there is no Google sign-in, dev key or server-side session here."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import Engine

from app import clock
from app.auth import require_user
from app.config import Settings, get_settings
from app.db import get_engine, load_sql
from app.demo.session import clear_demo_cookie, set_demo_cookie
from app.signin import SignedIn, SignInMethod

router = APIRouter(prefix="/auth")


@router.get("/method", response_model=SignInMethod)
def method() -> SignInMethod:
    """Tells the web app it is the demo, so it starts a demo visit instead of sign-in."""
    return SignInMethod(method="demo")


@router.post("/demo", status_code=204)
def start_demo(
    request: Request,
    response: Response,
    background: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> None:
    """Anyone may start a demo visit: it opens only synthetic data. No Origin check, unlike
    the real app: there is nothing to forge, since the visit itself is public. Rate
    limited (app/security.py). Never rebuilds the data itself; after answering, it asks
    for a rebuild if the data is over a day old (app/demo/self_heal.py)."""
    set_demo_cookie(response, settings)
    background.add_task(request.app.state.self_heal.check, engine, clock.now())


@router.get("/me", response_model=SignedIn)
def me(
    _visitor: Annotated[str, Depends(require_user)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> SignedIn:
    """Signed in, on the demo; with the numbers the tour quotes from the last rebuild."""
    with engine.connect() as conn:
        state = conn.execute(load_sql("demo/seed_state_read.sql")).first()
    return SignedIn(signed_in=True, demo=True, story=state.story if state else None)


@router.post("/logout", status_code=204)
def leave_demo(response: Response, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Ends the visit in this browser. Nothing is stored on the server to delete."""
    clear_demo_cookie(response, settings)
