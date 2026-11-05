"""Signing in and out (docs/AUTH_SPEC.md section 5): /auth/login, /auth/callback,
/auth/logout, /auth/me, /auth/method, and /auth/dev-login in local key mode only.

Google sign-in is OpenID Connect through Authlib (a vetted library: no hand-written JWT
checks). Authlib keeps the login's state, nonce and PKCE verifier in request.session, which
Starlette's SessionMiddleware stores in a short-lived signed cookie (see main.py). Google's
tokens are checked once, here, and then dropped: never stored, cached or logged.
"""

import hmac
import logging
from typing import Annotated

import httpx2
from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import Engine
from starlette.concurrency import run_in_threadpool

from app import clock
from app.auth import DEV_SUB, check_same_origin, client_ip, require_user
from app.config import Settings, get_settings
from app.db import get_engine
from app.errors import ApiError
from app.sessions import (
    clear_session_cookie,
    cookie_name,
    create_session,
    delete_session,
    set_session_cookie,
)

logger = logging.getLogger(__name__)

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
# openid gives the stable `sub`; email is Google's basic request. Nothing else.
SCOPES = "openid email"

DENIED_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Not authorized</title></head>
<body><h1>This account isn't authorized</h1><p><a href="/">Back to the app</a></p></body>
</html>"""


def google_client(
    settings: Settings, transport: httpx2.AsyncBaseTransport | None
) -> StarletteOAuth2App:
    """Google as an OpenID Connect provider, from its discovery document.

    `transport` is for tests only: a fake Google, so CI never calls the real one."""
    client_kwargs = {"scope": SCOPES, "code_challenge_method": "S256"}  # S256 = PKCE
    if transport is not None:
        client_kwargs["transport"] = transport
    oauth = OAuth()
    oauth.register(
        "google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret.get_secret_value(),
        server_metadata_url=GOOGLE_METADATA_URL,
        client_kwargs=client_kwargs,
    )
    return oauth.google


def safe_next(value: str | None) -> str:
    """Where to go after signing in: only a path on this site, never another site.

    "//evil.example" and "/\\evil.example" are read by browsers as another host."""
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return "/"


def callback_url(settings: Settings) -> str:
    """From PUBLIC_BASE_URL, never from the request's Host header (which a client sets)."""
    return settings.public_base_url.rstrip("/") + "/auth/callback"


def denied() -> HTMLResponse:
    """One generic page for every failure: it never says why."""
    return HTMLResponse(DENIED_PAGE, status_code=403)


def start_session(engine: Engine, sub: str) -> str:
    with engine.begin() as conn:
        return create_session(conn, sub, clock.now())


# --- Google: always registered in google mode --------------------------------------------

google_router = APIRouter(prefix="/auth")


@google_router.get("/login")
async def login(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    next: str | None = None,
) -> RedirectResponse:
    request.session.clear()  # a fresh login-state cookie for every attempt
    request.session["next"] = safe_next(next)
    google = request.app.state.google
    return await google.authorize_redirect(request, callback_url(settings))


@google_router.get("/callback", response_model=None)
async def callback(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> Response:
    next_path = safe_next(request.session.get("next"))
    google = request.app.state.google
    try:
        # Checks the state, swaps the code (with the PKCE verifier) for tokens, and
        # validates the ID token: Google's signature, iss, aud, exp and the nonce.
        token = await google.authorize_access_token(request)
    except Exception as error:  # noqa: BLE001 - any failure is a refusal, never a sign-in
        # The kind of failure only: messages can quote the code or the token.
        logger.warning("google_signin_failed error=%s", type(error).__name__)
        return denied()
    finally:
        request.session.clear()  # the state is single-use: a replayed callback fails

    claims = token.get("userinfo")  # None when Google sent no ID token: refused
    sub = claims.get("sub") if claims else None
    expected = settings.allowed_google_sub
    if not sub or expected is None or not hmac.compare_digest(sub, expected):
        # The sub only (no email, no token), so Rob can find his own on the first try.
        logger.warning("google_signin_denied sub=%s client=%s", sub, client_ip(request))
        return denied()

    session_id = await run_in_threadpool(start_session, engine, sub)
    response = RedirectResponse(next_path, status_code=303)
    set_session_cookie(response, settings, session_id)
    return response


# --- every mode -----------------------------------------------------------------------------

router = APIRouter(prefix="/auth")


class SignedIn(BaseModel):
    signed_in: bool
    demo: bool = False  # true only on the demo service: the web app shows "Demo data"
    # The demo only: numbers the tour quotes (streak_days, best_streak, n_checks, lift_day).
    story: dict | None = None


class SignInMethod(BaseModel):
    method: str  # "google", "key", or "demo" (the demo service)
    # The demo service's address, for the launch screen's Demo button; None if not set up.
    demo_url: str | None = None


@router.get("/method", response_model=SignInMethod)
def method(settings: Annotated[Settings, Depends(get_settings)]) -> SignInMethod:
    """Which sign-in screen to show: the Google button, or the dev key form (local only).

    Public, and not a secret: it lets one web build serve both modes (DECISIONS D112)."""
    return SignInMethod(method=settings.auth_mode, demo_url=settings.demo_public_url)


@router.get("/me", response_model=SignedIn)
def me(_sub: Annotated[str, Depends(require_user)]) -> SignedIn:
    """Signed in or 401. Nothing from Google: no email, no name."""
    return SignedIn(signed_in=True)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Engine, Depends(get_engine)],
    _sub: Annotated[str, Depends(require_user)],
) -> None:
    session_id = request.cookies.get(cookie_name(settings), "")
    with engine.begin() as conn:
        delete_session(conn, session_id)
    clear_session_cookie(response, settings)


# --- local key mode only (AUTH_MODE=key, APP_ENV=dev) ---------------------------------------

dev_router = APIRouter(prefix="/auth")


class DevLogin(BaseModel):
    key: str


@dev_router.post("/dev-login", status_code=204)
def dev_login(
    body: DevLogin,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> None:
    """The dev key form: the key becomes a normal session and is never stored in the browser."""
    check_same_origin(request, settings)
    expected = settings.dev_login_key.get_secret_value()
    if not hmac.compare_digest(body.key.encode(), expected.encode()):
        logger.warning("dev_login_failed client=%s", client_ip(request))
        raise ApiError(401, "unauthorized", "That key was not accepted.")
    set_session_cookie(response, settings, start_session(engine, DEV_SUB))
