"""Every route is public on purpose or guarded by exactly one credential type
(docs/AUTH_SPEC.md sections 6, 8 and the section 12 matrix)."""

import re

import pytest
from conftest import INGEST_HEADERS, ORIGIN, TEST_SETTINGS, app, sign_in
from sqlalchemy import text

from app.auth import DEV_SUB, allowed_sub

# Routes anyone may call. Adding a route that is neither here nor guarded fails CI.
PUBLIC = {
    ("GET", "/api/v1/health"),
    ("GET", "/auth/login"),
    ("GET", "/auth/callback"),
    ("GET", "/auth/method"),
}
INGEST = ("POST", "/api/v1/ingest/health")


def all_routes() -> list[tuple[str, str]]:
    """Every (method, path) the app serves, from its OpenAPI description.

    Black-box on purpose: FastAPI's internal route objects change between versions (0.142
    nests included routers), but the OpenAPI list is public and always complete."""
    paths = app.openapi()["paths"]
    return sorted(
        (method.upper(), path) for path, operations in paths.items() for method in operations
    )


def sample_path(path: str) -> str:
    """Fill path parameters such as {day} with a plausible value."""
    return re.sub(r"\{[^}]+\}", "2026-10-20", path)


def call(client, method: str, path: str, **kwargs):
    body = None if method in ("GET", "DELETE") else {}
    return client.request(method, sample_path(path), json=body, **kwargs)


def test_the_route_list_is_complete():
    routes = all_routes()
    assert INGEST in routes and ("GET", "/api/v1/dashboard") in routes
    assert len(routes) > 20


@pytest.mark.parametrize(("method", "path"), all_routes())
def test_every_route_is_public_on_purpose_or_401_without_a_credential(anonymous, method, path):
    response = call(anonymous, method, path)

    if (method, path) in PUBLIC:
        assert response.status_code != 401
    else:
        assert response.status_code == 401, f"{method} {path} is not protected"
        assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    ("method", "path"), [route for route in all_routes() if route != INGEST and route not in PUBLIC]
)
def test_the_ingest_token_opens_nothing_but_ingest(anonymous, method, path):
    assert call(anonymous, method, path, headers=INGEST_HEADERS).status_code == 401


def test_the_old_api_key_header_opens_nothing(anonymous):
    response = anonymous.get("/api/v1/dashboard", headers={"X-API-Key": "changemelocal"})

    assert response.status_code == 401


# --- sessions that no longer count ---------------------------------------------------------


def test_a_signed_in_client_gets_through(client):
    assert client.get("/api/v1/dashboard").status_code == 200


def test_a_session_for_another_google_account_is_401(anonymous, engine):
    sign_in(anonymous, engine, sub="canary-some-other-account")

    assert anonymous.get("/api/v1/dashboard").status_code == 401


def test_a_deleted_session_is_401(client, engine):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM app.session"))

    assert client.get("/api/v1/dashboard").status_code == 401


def test_an_expired_session_is_401(client, monkeypatch):
    monkeypatch.setenv("NOW_OVERRIDE", "2026-12-20T20:00:00+08:00")  # 61 days later

    assert client.get("/api/v1/dashboard").status_code == 401


def test_a_session_id_that_is_not_in_the_database_is_401(anonymous):
    anonymous.cookies.set("session", "canary-guessed-session-id")

    assert anonymous.get("/api/v1/dashboard").status_code == 401


def test_key_mode_has_its_own_account_so_switching_modes_signs_out():
    assert allowed_sub(TEST_SETTINGS) == TEST_SETTINGS.allowed_google_sub
    assert allowed_sub(TEST_SETTINGS.model_copy(update={"auth_mode": "key"})) == DEV_SUB


# --- CSRF: the Origin check and JSON only --------------------------------------------------

RECOVERY = "/api/v1/recovery"


@pytest.mark.parametrize("origin", [None, "https://evil.example", "http://testserver:8080"])
def test_a_change_without_the_apps_exact_origin_is_403(client, origin):
    headers = {"Origin": origin} if origin else {}
    if origin is None:
        del client.headers["Origin"]

    response = client.post(RECOVERY, json={"date": "2026-10-20"}, headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_origin"


def test_a_change_with_the_apps_origin_passes_the_check(client):
    response = client.post(RECOVERY, json={"date": "2026-10-20"}, headers={"Origin": ORIGIN})

    assert response.status_code not in (401, 403, 415)


def test_reading_needs_no_origin(client):
    del client.headers["Origin"]

    assert client.get("/api/v1/dashboard").status_code == 200


@pytest.mark.parametrize(
    "content_type", ["application/x-www-form-urlencoded", "text/plain", "multipart/form-data"]
)
def test_a_change_that_is_not_json_is_415(client, content_type):
    response = client.post(
        RECOVERY, content=b"date=2026-10-20", headers={"Content-Type": content_type}
    )

    assert response.status_code == 415


def test_a_delete_without_a_body_needs_no_content_type(client):
    response = client.delete("/api/v1/vacation")

    assert response.status_code not in (401, 403, 415)
