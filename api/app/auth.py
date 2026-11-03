"""Who may call the API (docs/AUTH_SPEC.md sections 7 and 8).

require_api_key: the old shared key, still on the web app's routes until sessions replace
it (AUTH_SPEC step 4).
require_ingest_token: the iOS Shortcut's bearer token, on POST /api/v1/ingest/health only.
"""

import hashlib
import hmac
import logging
import os
import secrets
from typing import Annotated

from fastapi import Depends, Header, Request

from app.config import Settings, get_settings
from app.errors import ApiError

logger = logging.getLogger(__name__)

BEARER = "Bearer "


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """FastAPI dependency: reads the X-API-Key header (FastAPI maps the name)."""
    expected = os.environ["API_KEY"]
    # compare_digest takes the same time wherever the strings differ, so response
    # timing cannot be used to guess the key one character at a time.
    if x_api_key is None or not secrets.compare_digest(x_api_key.encode(), expected.encode()):
        raise ApiError(401, "unauthorized", "Missing or wrong X-API-Key header.")


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
    query string, a cookie or a body field. Every failure gets the same answer."""
    if is_valid_ingest_token(authorization, settings):
        return
    # The event, where from and which route; never the header itself.
    client = request.client.host if request.client else "unknown"
    logger.warning("ingest_unauthorized client=%s route=%s", client, request.url.path)
    raise ApiError(401, "unauthorized", "Unauthorized.")
