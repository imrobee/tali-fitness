"""Server-side sessions and the session cookie (docs/AUTH_SPEC.md section 6).

Sign-in creates a new random id, sends it to the browser in an HttpOnly cookie, and keeps
only its SHA-256 in app.session. A request is signed in when the hash of its cookie is in
the table, the session is younger than SESSION_ABSOLUTE_DAYS, and it was used within the
last SESSION_IDLE_DAYS.

Why server-side rather than a signed cookie: signing out (or a stolen cookie) can be
ended on the server by deleting one row.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Response
from sqlalchemy import Connection

from app.config import SESSION_ABSOLUTE_DAYS, SESSION_IDLE_DAYS, Settings
from app.db import load_sql

# How often last_seen_at is written: once an hour is enough for a 30-day idle limit, and
# saves a database write on every request.
TOUCH_EVERY = timedelta(hours=1)
ABSOLUTE = timedelta(days=SESSION_ABSOLUTE_DAYS)
IDLE = timedelta(days=SESSION_IDLE_DAYS)


def session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def create_session(conn: Connection, sub: str, now: datetime) -> str:
    """Start a session for `sub` and return its id (the cookie value), shown only here.

    Always a new id, never one the browser sent: that prevents session fixation. Expired
    sessions are cleared out at the same time.
    """
    conn.execute(
        load_sql("auth/session_delete_expired.sql"), {"now": now, "idle_cutoff": now - IDLE}
    )
    session_id = secrets.token_urlsafe(32)  # 256 random bits
    conn.execute(
        load_sql("auth/session_insert.sql"),
        {
            "session_hash": session_hash(session_id),
            "sub": sub,
            "now": now,
            "expires_at": now + ABSOLUTE,
        },
    )
    return session_id


def find_session(conn: Connection, session_id: str, now: datetime) -> str | None:
    """The signed-in `sub` for this cookie value, or None if it is unknown or expired."""
    hashed = session_hash(session_id)
    row = conn.execute(load_sql("auth/session_find.sql"), {"session_hash": hashed}).first()
    if row is None:
        return None
    if now >= row.expires_at or now - row.last_seen_at > IDLE:
        return None
    if now - row.last_seen_at >= TOUCH_EVERY:
        conn.execute(load_sql("auth/session_touch.sql"), {"session_hash": hashed, "now": now})
    return row.sub


def delete_session(conn: Connection, session_id: str) -> None:
    conn.execute(load_sql("auth/session_delete.sql"), {"session_hash": session_hash(session_id)})


def cookie_name(settings: Settings) -> str:
    """__Host- makes the browser insist on Secure, Path=/ and no Domain, so only HTTPS
    production can use it; dev on plain HTTP (this Mac, the LAN) uses a plain name."""
    return "__Host-session" if settings.cookie_secure else "session"


def set_session_cookie(response: Response, settings: Settings, session_id: str) -> None:
    # HttpOnly: page scripts cannot read it. SameSite=Lax: other sites' forms and fetches
    # do not carry it. No domain: only this host gets it.
    response.set_cookie(
        cookie_name(settings),
        session_id,
        max_age=int(ABSOLUTE.total_seconds()),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        cookie_name(settings),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
