"""API key check for every endpoint except /health (ARCHITECTURE.md section 12)."""

import os
import secrets
from typing import Annotated

from fastapi import Header

from app.errors import ApiError


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """FastAPI dependency: reads the X-API-Key header (FastAPI maps the name)."""
    expected = os.environ["API_KEY"]
    # compare_digest takes the same time wherever the strings differ, so response
    # timing cannot be used to guess the key one character at a time.
    if x_api_key is None or not secrets.compare_digest(x_api_key.encode(), expected.encode()):
        raise ApiError(401, "unauthorized", "Missing or wrong X-API-Key header.")
