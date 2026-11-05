"""The demo service's /auth routes. They replace the real ones, which are not mounted in
demo mode: there is no Google sign-in, dev key or server-side session here."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.auth import require_user
from app.config import Settings, get_settings
from app.demo.session import clear_demo_cookie, set_demo_cookie
from app.signin import SignedIn, SignInMethod

router = APIRouter(prefix="/auth")


@router.get("/method", response_model=SignInMethod)
def method() -> SignInMethod:
    """Tells the web app it is the demo, so it starts a demo visit instead of sign-in."""
    return SignInMethod(method="demo")


@router.post("/demo", status_code=204)
def start_demo(response: Response, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Anyone may start a demo visit: it opens only synthetic data. No Origin check, unlike
    the real app: there is nothing to forge, since the visit itself is public. Rate
    limited (app/security.py)."""
    set_demo_cookie(response, settings)


@router.get("/me", response_model=SignedIn)
def me(_visitor: Annotated[str, Depends(require_user)]) -> SignedIn:
    return SignedIn(signed_in=True, demo=True)


@router.post("/logout", status_code=204)
def leave_demo(response: Response, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Ends the visit in this browser. Nothing is stored on the server to delete."""
    clear_demo_cookie(response, settings)
