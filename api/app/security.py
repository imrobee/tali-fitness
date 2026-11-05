"""Hardening (docs/AUTH_SPEC.md section 10): security headers, rate limits, and a generic
500 that never shows a stack trace.
"""

import logging
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth import client_ip
from app.config import Settings

logger = logging.getLogger(__name__)

# Every response: nothing may load from elsewhere, frame the page, or leak the URL onward.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
        "accelerometer=(), gyroscope=(), magnetometer=(), interest-cohort=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    # Signed-in data and sign-in answers must never sit in a browser or proxy cache.
    "Cache-Control": "no-store",
}
# HTTPS only: a browser that has seen this refuses plain HTTP to the host for a year.
HSTS = "max-age=31536000"

# (requests, per seconds) by route. Sign-in pages are what a guesser hits; the Shortcut
# posts a few times a day. /auth/me and /auth/method are not limited: the app asks them on
# every load, and they reveal nothing without a valid session.
LIMITS = {
    "dev_login": (5, 60),
    "sign_in": (10, 60),
    "ingest": (60, 60),
    # The demo is public: starting visits, and reading pages. A page load makes about 8
    # requests, so 120 a minute is ~15 page views a minute from one address.
    "demo_start": (10, 60),
    "demo_read": (120, 60),
}

# The demo accepts these writes only; neither touches the database. Everything else that
# is not a read gets 403, whatever route it names (DECISIONS D118).
DEMO_ALLOWED_WRITES = {("POST", "/auth/demo"), ("POST", "/auth/logout")}
READ_METHODS = {"GET", "HEAD", "OPTIONS"}
# Demo requests carry no body worth more than this (the two writes above send none).
DEMO_MAX_BODY_BYTES = 1024
DEMO_READ_ONLY = "Demo mode: changes aren't saved."


def limit_for(path: str, demo: bool = False) -> str | None:
    if demo:
        if path == "/auth/demo":
            return "demo_start"
        if path.startswith("/api/v1/"):
            return "demo_read"
        return None
    if path == "/auth/dev-login":
        return "dev_login"
    if path in ("/auth/login", "/auth/callback"):
        return "sign_in"
    if path == "/api/v1/ingest/health":
        return "ingest"
    return None


class RateLimiter:
    """In memory, per (limit, client IP): the times of recent requests in a sliding window.

    One API instance, so a dictionary is enough (DECISIONS D107)."""

    def __init__(self) -> None:
        self.recent: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def allow(self, name: str, client: str, now: float) -> bool:
        count, seconds = LIMITS[name]
        times = self.recent[(name, client)]
        while times and times[0] <= now - seconds:
            times.popleft()  # older than the window
        if len(times) >= count:
            return False
        times.append(now)
        return True


def error_response(status: int, code: str, message: str, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
        headers=headers,
    )


def demo_refusal(request: Request) -> JSONResponse | None:
    """The demo's server-side read-only rule, before any route runs. None = let it through."""
    content_length = request.headers.get("content-length")
    if request.headers.get("transfer-encoding") or (
        content_length and int(content_length) > DEMO_MAX_BODY_BYTES
    ):
        return error_response(413, "payload_too_large", "Too large for the demo.")
    if request.method in READ_METHODS:
        return None
    if (request.method, request.url.path) in DEMO_ALLOWED_WRITES:
        return None
    return error_response(403, "demo_read_only", DEMO_READ_ONLY)


def add_hardening(app: FastAPI, settings: Settings) -> None:
    app.state.rate_limiter = RateLimiter()
    demo = settings.app_env == "demo"

    if demo:
        # Registered first, so it runs after the rate limit (Starlette runs the last-added
        # middleware first): a flood of writes is still counted and slowed.
        @app.middleware("http")
        async def read_only(request: Request, call_next):
            refusal = demo_refusal(request)
            if refusal is not None:
                return refusal
            return await call_next(request)

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        name = limit_for(request.url.path, demo)
        if name is not None:
            limiter: RateLimiter = request.app.state.rate_limiter
            if not limiter.allow(name, client_ip(request), time.monotonic()):
                logger.warning("rate_limited limit=%s client=%s", name, client_ip(request))
                return error_response(
                    429,
                    "rate_limited",
                    "Too many requests.",
                    headers={"Retry-After": str(LIMITS[name][1])},
                )
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = HSTS
        return response

    @app.exception_handler(Exception)
    async def internal_error(request: Request, error: Exception) -> JSONResponse:
        # The kind of error only: its message or traceback could quote data or a secret.
        logger.error("internal_error type=%s route=%s", type(error).__name__, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Something went wrong."}},
        )
