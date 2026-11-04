"""No credential ever reaches a log or a response body (docs/AUTH_SPEC.md section 11).

Runs the full sign-in, a denied sign-in, failed and good ingests, the dev key form and
sign-out with canary secrets, captures every log record (DEBUG and up) and every response,
then looks for each secret. The session cookie may appear only in its own Set-Cookie header.
"""

import logging
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import (
    FAKE_GOOGLE,
    INGEST_HEADERS,
    ORIGIN,
    TEST_INGEST_TOKEN,
    TEST_SETTINGS,
    load_sample,
)
from fake_google import ACCESS_TOKEN, CLIENT_SECRET, EMAIL
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.db import get_engine
from app.main import create_app

DEV_KEY = "canary-dev-login-key-for-leak-test"
WRONG_INGEST_TOKEN = "ing_canary-wrong-token-for-leak-test"
STATE_SECRET = TEST_SETTINGS.oauth_state_secret.get_secret_value()


class Recorder:
    """Every response's body and headers, apart from the places a value must go: the session
    cookie's Set-Cookie, the login-state cookie, and the redirect that takes the state to
    Google."""

    def __init__(self) -> None:
        self.seen: list[str] = []
        self.session_ids: list[str] = []
        self.oauth_values: list[str] = []  # codes and states that passed through the browser

    def add(self, response) -> None:
        self.seen.append(response.text)
        for name, value in response.headers.items():
            name = name.lower()
            if name == "set-cookie" and value.startswith("session="):
                session_id = value.split(";")[0].removeprefix("session=")
                if session_id.strip('"'):  # sign-out sends an empty cookie
                    self.session_ids.append(session_id)
            elif name == "set-cookie" and value.startswith("login_state="):
                continue
            elif name == "location" and value.startswith("https://accounts.google.com/"):
                continue
            else:
                self.seen.append(f"{name}: {value}")
        location = response.headers.get("location", "")
        query = parse_qs(urlsplit(location).query)
        self.oauth_values += query.get("state", []) + query.get("code_challenge", [])


def google_round_trip(client: TestClient, recorder: Recorder) -> None:
    login = client.get("/auth/login", follow_redirects=False)
    recorder.add(login)
    code, state = FAKE_GOOGLE.approve(login.headers["location"])
    recorder.oauth_values += [code, state]
    recorder.add(
        client.get("/auth/callback", params={"code": code, "state": state}, follow_redirects=False)
    )


def from_test_client(record: logging.LogRecord) -> bool:
    """The test client (httpx2) logging the URLs it calls on the app: the browser's side of
    the conversation, which the server never logs. The app's own httpx2 calls to Google
    stay in the check."""
    return record.name == "httpx2" and "http://testserver/" in record.getMessage()


@pytest.fixture
def records(caplog):
    caplog.set_level(logging.DEBUG)
    return caplog


def test_no_secret_reaches_a_log_or_a_response(anonymous, engine, records, monkeypatch):
    recorder = Recorder()

    # 1. Google sign-in, the allowed account; then a look around and sign-out.
    google_round_trip(anonymous, recorder)
    recorder.add(anonymous.get("/auth/me"))
    recorder.add(anonymous.get("/api/v1/dashboard"))
    recorder.add(anonymous.post("/auth/logout"))

    # 2. A denied account, then a tampered callback.
    FAKE_GOOGLE.sub = "canary-somebody-else"
    google_round_trip(anonymous, recorder)
    id_tokens = list(FAKE_GOOGLE.id_tokens_issued)
    recorder.add(
        anonymous.get("/auth/callback", params={"code": "canary-code-x", "state": "canary-x"})
    )

    # 3. The Shortcut: a wrong token, then the right one.
    body = load_sample("health_payload_01.json")
    wrong = {"Authorization": f"Bearer {WRONG_INGEST_TOKEN}"}
    recorder.add(anonymous.post("/api/v1/ingest/health", json=body, headers=wrong))
    recorder.add(anonymous.post("/api/v1/ingest/health", json=body, headers=INGEST_HEADERS))

    # 4. The dev key form, wrong then right.
    monkeypatch.setenv("APP_ENV", "dev")
    settings = TEST_SETTINGS.model_copy(
        update={"app_env": "dev", "auth_mode": "key", "dev_login_key": SecretStr(DEV_KEY)}
    )
    local = create_app(settings)
    local.dependency_overrides[get_engine] = lambda: engine
    dev = TestClient(local, headers={"Origin": ORIGIN})
    recorder.add(dev.post("/auth/dev-login", json={"key": "canary-wrong-dev-key"}))
    recorder.add(dev.post("/auth/dev-login", json={"key": DEV_KEY}))

    secrets = [
        CLIENT_SECRET,
        STATE_SECRET,
        ACCESS_TOKEN,
        EMAIL,
        TEST_INGEST_TOKEN,
        WRONG_INGEST_TOKEN,
        DEV_KEY,
        "canary-wrong-dev-key",
        *id_tokens,
        *recorder.session_ids,
        *recorder.oauth_values,
    ]
    assert len(recorder.session_ids) == 2 and len(id_tokens) == 2 and recorder.oauth_values
    logs = "\n".join(r.getMessage() for r in records.records if not from_test_client(r))
    responses = "\n".join(recorder.seen)
    for secret in secrets:
        assert secret not in logs, f"a secret reached the logs: {secret[:12]}..."
        assert secret not in responses, f"a secret reached a response: {secret[:12]}..."
    assert "ing_" not in logs
