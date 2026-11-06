"""Running on Vercel (DECISIONS D131, D134): the database engine pools nothing itself (Neon's
pooler does), SQL is found without the container's /db mount, and the client's address
comes from Vercel's own header."""

from types import SimpleNamespace

from sqlalchemy.pool import NullPool
from starlette.requests import Request

from app import db
from app.auth import client_ip


def test_on_vercel_the_engine_keeps_no_pool(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    db.get_engine.cache_clear()
    try:
        engine = db.get_engine()
        assert isinstance(engine.pool, NullPool)
    finally:
        db.get_engine.cache_clear()


def test_locally_the_engine_keeps_a_pool(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    db.get_engine.cache_clear()
    try:
        assert not isinstance(db.get_engine().pool, NullPool)
    finally:
        db.get_engine.cache_clear()


def test_sql_is_found_next_to_the_code():
    # In this container the code is /app/app and db/ is mounted at /db; on Vercel both sit
    # in the repository. Either way: two folders up, then db/sql.
    assert (db.SQL_DIR / "api" / "streak.sql").is_file()


def request(headers: dict[str, str], vercel: bool) -> Request:
    app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(vercel=vercel)))
    scope = {
        "type": "http",
        "headers": [(key.encode(), value.encode()) for key, value in headers.items()],
        "client": ("10.0.0.9", 1234),
        "app": app,
    }
    return Request(scope)


def test_on_vercel_the_client_is_vercels_forwarded_address():
    headers = {"x-vercel-forwarded-for": "203.0.113.7", "x-forwarded-for": "198.51.100.1"}

    assert client_ip(request(headers, vercel=True)) == "203.0.113.7"


def test_elsewhere_the_client_is_the_connection():
    headers = {"x-vercel-forwarded-for": "203.0.113.7"}  # a header anyone could send

    assert client_ip(request(headers, vercel=False)) == "10.0.0.9"
