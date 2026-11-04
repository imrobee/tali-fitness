"""Server-side sessions and the session cookie (docs/AUTH_SPEC.md section 6)."""

from datetime import UTC, datetime, timedelta

from conftest import TEST_SETTINGS
from fastapi import Response
from sqlalchemy import text

from app.sessions import (
    clear_session_cookie,
    create_session,
    delete_session,
    find_session,
    session_hash,
    set_session_cookie,
)

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
SUB = "canary-google-sub-0001"


def start(engine, now=NOW) -> str:
    with engine.begin() as conn:
        return create_session(conn, SUB, now)


def find(engine, session_id: str, now=NOW) -> str | None:
    with engine.begin() as conn:
        return find_session(conn, session_id, now)


def stored(engine) -> list:
    with engine.connect() as conn:
        return conn.execute(text("SELECT * FROM app.session")).mappings().all()


def test_a_new_session_is_found_by_its_cookie_value(engine):
    session_id = start(engine)

    assert find(engine, session_id) == SUB


def test_the_database_keeps_only_the_hash_of_the_id(engine):
    session_id = start(engine)

    [row] = stored(engine)
    assert row["session_hash"] == session_hash(session_id)
    assert session_id not in str(dict(row))


def test_every_sign_in_gets_a_new_256_bit_id(engine):
    first, second = start(engine), start(engine)

    assert first != second
    assert len(first) == 43  # token_urlsafe(32): 32 random bytes in URL-safe base64


def test_unknown_ids_and_guessed_hashes_are_not_signed_in(engine):
    session_id = start(engine)

    assert find(engine, "not-a-session") is None
    # Presenting the stored hash as the cookie does not work: it gets hashed again.
    assert find(engine, session_hash(session_id)) is None


def test_a_session_ends_after_60_days_even_when_used_daily(engine):
    session_id = start(engine)
    for day in range(1, 60):
        assert find(engine, session_id, NOW + timedelta(days=day)) == SUB

    assert find(engine, session_id, NOW + timedelta(days=60)) is None


def test_a_session_unused_for_more_than_30_days_ends(engine):
    session_id = start(engine)

    assert find(engine, session_id, NOW + timedelta(days=30)) == SUB
    assert find(engine, session_id, NOW + timedelta(days=61)) is None
    fresh = start(engine)
    assert find(engine, fresh, NOW + timedelta(days=30, seconds=1)) is None


def test_last_seen_is_written_at_most_once_an_hour(engine):
    session_id = start(engine)

    find(engine, session_id, NOW + timedelta(minutes=59))
    assert stored(engine)[0]["last_seen_at"] == NOW

    find(engine, session_id, NOW + timedelta(hours=1))
    assert stored(engine)[0]["last_seen_at"] == NOW + timedelta(hours=1)


def test_a_deleted_session_is_signed_out(engine):
    session_id = start(engine)
    with engine.begin() as conn:
        delete_session(conn, session_id)

    assert find(engine, session_id) is None


def test_signing_in_clears_out_expired_and_idle_sessions(engine):
    start(engine, NOW - timedelta(days=61))  # expired
    idle = start(engine, NOW - timedelta(days=40))  # idle since then
    start(engine)

    remaining = {row["session_hash"] for row in stored(engine)}
    assert session_hash(idle) not in remaining
    assert len(remaining) == 1


# --- the cookie ----------------------------------------------------------------------------


def cookie_header(settings) -> str:
    response = Response()
    set_session_cookie(response, settings, "canary-session-id")
    return response.headers["set-cookie"]


def test_the_dev_cookie_is_httponly_lax_and_lasts_60_days():
    header = cookie_header(TEST_SETTINGS)

    assert header.startswith("session=canary-session-id;")
    assert "HttpOnly" in header
    assert "SameSite=lax" in header
    assert "Max-Age=5184000" in header  # 60 days
    assert "Path=/" in header
    assert "Domain" not in header
    assert "Secure" not in header  # plain HTTP on this Mac and the LAN


def test_the_production_cookie_is_a_secure_host_cookie():
    header = cookie_header(TEST_SETTINGS.model_copy(update={"app_env": "production"}))

    assert header.startswith("__Host-session=canary-session-id;")
    assert "Secure" in header
    assert "HttpOnly" in header
    assert "Path=/" in header
    assert "Domain" not in header


def test_signing_out_expires_the_cookie():
    response = Response()
    clear_session_cookie(response, TEST_SETTINGS)

    header = response.headers["set-cookie"]
    assert header.startswith("session=")
    assert "Max-Age=0" in header
