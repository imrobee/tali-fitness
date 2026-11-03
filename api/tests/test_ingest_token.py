"""The Shortcut's ingest token (docs/AUTH_SPEC.md section 7 and the section 12 matrix)."""

import json
import logging

import pytest
from conftest import INGEST_HEADERS, TEST_API_KEY, TEST_INGEST_TOKEN, TEST_SETTINGS, load_sample
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.auth import token_hash
from app.db import get_engine
from app.main import create_app

URL = "/api/v1/ingest/health"
UNAUTHORIZED = {"error": {"code": "unauthorized", "message": "Unauthorized."}}
NEXT_TOKEN = "ing_canary-next-token-not-a-real-secret"


def post(client: TestClient, headers: dict | None = None, url: str = URL):
    body = json.dumps(load_sample("health_payload_01.json"))
    return client.post(url, content=body, headers=headers or {})


def test_a_valid_token_is_accepted(client):
    assert post(client, INGEST_HEADERS).status_code == 201


@pytest.mark.parametrize(
    "headers",
    [
        {},  # missing
        {"Authorization": TEST_INGEST_TOKEN},  # no "Bearer "
        {"Authorization": "Basic " + TEST_INGEST_TOKEN},  # another scheme
        {"Authorization": "Bearer ing_wrong-token"},
        {"Authorization": "Bearer "},
        {"X-API-Key": TEST_API_KEY},  # the old key does not open this route
    ],
)
def test_every_failure_gets_the_same_401(client, headers):
    response = post(client, headers)

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


def test_the_token_is_never_read_from_a_query_string_or_cookie(client):
    assert post(client, url=f"{URL}?token={TEST_INGEST_TOKEN}").status_code == 401

    client.cookies.set("Authorization", f"Bearer {TEST_INGEST_TOKEN}")
    assert post(client).status_code == 401


def test_a_failure_is_logged_without_the_token(client, caplog):
    with caplog.at_level(logging.WARNING, logger="app.auth"):
        post(client, {"Authorization": "Bearer ing_wrong-token"})

    assert "ingest_unauthorized" in caplog.text
    assert "ing_" not in caplog.text


def test_the_token_does_not_open_other_routes(client):
    response = client.get("/api/v1/dashboard", headers=INGEST_HEADERS)

    assert response.status_code == 401


def test_rotation_accepts_both_tokens_until_the_old_hash_is_removed(engine, monkeypatch):
    monkeypatch.setenv("NOW_OVERRIDE", "2026-10-20T20:00:00+08:00")

    def client_for(**hashes) -> TestClient:
        settings = TEST_SETTINGS.model_copy(update=hashes)
        rotating = create_app(settings)
        rotating.dependency_overrides[get_engine] = lambda: engine
        return TestClient(rotating)

    old, new = INGEST_HEADERS, {"Authorization": f"Bearer {NEXT_TOKEN}"}
    during = client_for(ingest_token_sha256_next=SecretStr(token_hash(NEXT_TOKEN)))
    assert post(during, old).status_code in (200, 201)
    assert post(during, new).status_code in (200, 201)

    after = client_for(ingest_token_sha256=SecretStr(token_hash(NEXT_TOKEN)))
    assert post(after, old).status_code == 401
    assert post(after, new).status_code in (200, 201)
