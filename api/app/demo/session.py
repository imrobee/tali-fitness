"""The demo visitor's cookie (DECISIONS D118).

A signed cookie, not a row in app.session: the demo's database role can only read, so the
demo cannot store sessions, and it has nothing to protect that a server-side session
would add (anyone may start one). The signature stops a forged or edited cookie; the
timestamp inside makes it expire.

It is a different cookie from the real app's ("demo_session", not "session"), signed with
a secret the real app never has, and the real app never reads it.
"""

from fastapi import Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import Settings

DEMO_SESSION_HOURS = 2
MAX_AGE = DEMO_SESSION_HOURS * 3600
# Why a salt: the same secret signing something else in future could never produce a
# value that also passes as a demo cookie.
SALT = "demo-session"
PAYLOAD = {"kind": "demo"}


def demo_cookie_name(settings: Settings) -> str:
    """As the real session cookie: the __Host- prefix whenever the demo is on HTTPS."""
    return "__Host-demo_session" if settings.cookie_secure else "demo_session"


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.demo_session_secret.get_secret_value(), salt=SALT)


def new_demo_cookie(settings: Settings) -> str:
    return _serializer(settings).dumps(PAYLOAD)


def is_demo_visitor(request: Request, settings: Settings) -> bool:
    """True for a cookie this demo signed in the last two hours, saying kind=demo."""
    value = request.cookies.get(demo_cookie_name(settings))
    if not value:
        return False
    try:
        payload = _serializer(settings).loads(value, max_age=MAX_AGE)
    except BadSignature:  # also covers SignatureExpired
        return False
    return payload == PAYLOAD


def set_demo_cookie(response: Response, settings: Settings) -> None:
    response.set_cookie(
        demo_cookie_name(settings),
        new_demo_cookie(settings),
        max_age=MAX_AGE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


def clear_demo_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        demo_cookie_name(settings),
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
