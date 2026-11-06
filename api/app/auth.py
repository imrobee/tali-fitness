"""Who may call the API (docs/AUTH_SPEC.md sections 6, 7 and 8).

Exactly one of two FastAPI dependencies guards every route except GET /api/v1/health:
- require_user: a signed-in browser (the session cookie), for the web app's routes.
- require_ingest_token: the iOS Shortcut's bearer token, for POST /api/v1/ingest/health.
"""

import hashlib
import hmac
import logging
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import Engine

from app import clock
from app.config import Settings, get_settings
from app.db import get_engine
from app.demo.session import is_demo_visitor
from app.errors import ApiError
from app.sessions import cookie_name, find_session

logger = logging.getLogger(__name__)

BEARER = "Bearer "
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# The `sub` of a session made by the dev key form (AUTH_MODE=key, dev only). Switching
# AUTH_MODE therefore ends the other mode's sessions.
DEV_SUB = "dev-login"
# What require_user returns on the demo service: a visitor, never an account.
DEMO_VISITOR = "demo-visitor"


def client_ip(request: Request) -> str:
    """The visitor's address, for rate limits and logs. On Vercel, from Vercel's own
    x-vercel-forwarded-for header: Vercel sets it and overwrites what the client sends
    (docs: "Request headers"), so it can't be faked. Elsewhere, from the connection
    (Uvicorn takes it from X-Forwarded-For only from FORWARDED_ALLOW_IPS)."""
    settings = getattr(request.app.state, "settings", None)
    if settings is not None and settings.vercel:
        forwarded = request.headers.get("x-vercel-forwarded-for", "")
        return forwarded.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


# --- the web app: session cookie -----------------------------------------------------------


def allowed_sub(settings: Settings) -> str | None:
    """The one account that may be signed in: the Google `sub`, or the dev key's stand-in."""
    if settings.auth_mode == "key":
        return DEV_SUB
    return settings.allowed_google_sub


def check_same_origin(request: Request, settings: Settings) -> None:
    """CSRF protection for cookie-authenticated requests that change something.

    Browsers send Origin on every cross-site POST/PUT/DELETE, and another site cannot fake
    it, so an exact match proves the request came from this app's own pages. JSON only:
    an HTML form on another site can send form data or plain text, but never JSON.
    """
    if request.method in SAFE_METHODS:
        return
    if request.headers.get("origin") != settings.public_origin:
        logger.warning("origin_rejected method=%s route=%s", request.method, request.url.path)
        raise ApiError(403, "forbidden_origin", "This request did not come from the app.")
    content_type = request.headers.get("content-type", "")
    has_body = int(request.headers.get("content-length") or 0) > 0
    if (content_type or has_body) and not content_type.startswith("application/json"):
        raise ApiError(415, "unsupported_media_type", "Send JSON.")


def require_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> str:
    """FastAPI dependency: a valid session for the allowed account. Returns its `sub`.

    On the demo service, only a demo cookie counts, and app.session is never read: the
    demo has no accounts, and its database role could not read real sessions anyway."""
    if settings.app_env == "demo":
        if is_demo_visitor(request, settings):
            return DEMO_VISITOR
        raise ApiError(401, "unauthorized", "Start the demo first.")
    check_same_origin(request, settings)
    session_id = request.cookies.get(cookie_name(settings))
    sub = None
    if session_id:
        with engine.begin() as conn:
            sub = find_session(conn, session_id, clock.now())
    # Changing ALLOWED_GOOGLE_SUB ends every session of the old account at once: that is
    # the recovery path if the account is ever compromised (no backdoor, no break-glass key).
    expected = allowed_sub(settings)
    if sub is None or expected is None or not hmac.compare_digest(sub, expected):
        raise ApiError(401, "unauthorized", "Sign in first.")
    return sub


# --- the iOS Shortcut: bearer token --------------------------------------------------------


def token_hash(token: str) -> str:
    """The SHA-256 hex the server keeps instead of the token (as make_ingest_token.py)."""
    return hashlib.sha256(token.encode()).hexdigest()


def accepted_hashes(settings: Settings) -> list[str]:
    """The current hash, plus the next one while a new token is being rolled out."""
    hashes = [settings.ingest_token_sha256, settings.ingest_token_sha256_next]
    return [value.get_secret_value() for value in hashes if value is not None]


def is_valid_ingest_token(authorization: str | None, settings: Settings) -> bool:
    """True only for "Bearer <token>" whose hash is one of the accepted hashes."""
    if authorization is None or not authorization.startswith(BEARER):
        return False
    presented = token_hash(authorization.removeprefix(BEARER))
    # Compare against every accepted hash (no early exit), each in constant time.
    matches = [hmac.compare_digest(presented, expected) for expected in accepted_hashes(settings)]
    return any(matches)


def require_ingest_token(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """FastAPI dependency for the Shortcut. Only the Authorization header counts: never a
    query string, a cookie or a body field. Every failure gets the same answer.

    No Origin check here: the Shortcut is not a browser, and a browser never attaches
    this header on its own, so another site cannot make it send one (no CSRF risk)."""
    if is_valid_ingest_token(authorization, settings):
        return
    # The event, where from and which route; never the header itself.
    logger.warning("ingest_unauthorized client=%s route=%s", client_ip(request), request.url.path)
    raise ApiError(401, "unauthorized", "Unauthorized.")
