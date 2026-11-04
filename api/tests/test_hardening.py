"""Headers, rate limits, production hygiene and log redaction (docs/AUTH_SPEC.md 10, 12)."""

import logging
import time
from collections import deque

import pytest
from conftest import FAKE_GOOGLE, TEST_SETTINGS, app
from fake_google import CLIENT_SECRET
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.logs import REDACTED, RedactingFilter, install_log_redaction, redact
from app.main import create_app
from app.security import RateLimiter

EXPECTED_HEADERS = {
    "content-security-policy": "default-src 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=()",
    "cross-origin-opener-policy": "same-origin",
    "cache-control": "no-store",
}


def production_app() -> TestClient:
    settings = TEST_SETTINGS.model_copy(
        update={
            "app_env": "production",
            "public_base_url": "https://tracker.example.com",
            "allowed_google_sub": "canary-google-sub-0001",
        }
    )
    return TestClient(create_app(settings, google_transport=FAKE_GOOGLE.transport))


# --- headers ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["/api/v1/health", "/api/v1/dashboard", "/auth/me", "/auth/method"]
)
def test_every_answer_carries_the_security_headers(anonymous, path):
    response = anonymous.get(path)

    for name, start in EXPECTED_HEADERS.items():
        assert response.headers[name].startswith(start), name


def test_signed_in_answers_are_never_cached(client):
    assert client.get("/api/v1/dashboard").headers["cache-control"] == "no-store"


def test_hsts_only_in_production(anonymous):
    assert "strict-transport-security" not in anonymous.get("/api/v1/health").headers

    header = production_app().get("/api/v1/health").headers["strict-transport-security"]
    assert header == "max-age=31536000"


# --- production hygiene ----------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_the_api_docs_are_off_in_production(path):
    assert production_app().get(path).status_code == 404


def test_the_api_docs_stay_on_in_dev_and_test(anonymous):
    assert anonymous.get("/openapi.json").status_code == 200


def test_a_crash_answers_a_generic_500_without_a_trace():
    crashing = create_app(TEST_SETTINGS, google_transport=FAKE_GOOGLE.transport)

    def boom():
        raise RuntimeError("canary-internal-detail")

    crashing.add_api_route("/boom", boom)
    response = TestClient(crashing, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong."}
    }
    assert "canary" not in response.text and "Traceback" not in response.text


# --- rate limits -----------------------------------------------------------------------------


def test_the_11th_sign_in_request_in_a_minute_is_429(anonymous):
    for _ in range(10):
        assert anonymous.get("/auth/login", follow_redirects=False).status_code == 302

    response = anonymous.get("/auth/login", follow_redirects=False)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert response.headers["retry-after"] == "60"


def test_the_app_itself_is_not_limited(client):
    for _ in range(30):
        assert client.get("/auth/me").status_code == 200


@pytest.mark.parametrize(("name", "count"), [("dev_login", 5), ("sign_in", 10), ("ingest", 60)])
def test_each_limit_resets_after_a_minute_and_is_per_client(name, count):
    limiter = RateLimiter()
    for _ in range(count):
        assert limiter.allow(name, "10.0.0.1", now=100.0)

    assert not limiter.allow(name, "10.0.0.1", now=100.0)
    assert limiter.allow(name, "10.0.0.2", now=100.0)  # another client has its own count
    assert limiter.allow(name, "10.0.0.1", now=160.1)  # a minute later


def test_the_ingest_route_is_limited(anonymous):
    # 60 requests from the test client in the last moment: the 61st is refused.
    app.state.rate_limiter.recent[("ingest", "testclient")] = deque([time.monotonic()] * 60)

    assert anonymous.post("/api/v1/ingest/health", json={}).status_code == 429


# --- log redaction ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "Authorization: Bearer ing_canary-token-1234",
        "headers={'authorization': 'Bearer canary-session'}",
        "Cookie: session=canary-session-id",
        "set-cookie=session=canary-session-id",
        'body {"client_secret": "canary-secret", "code": "canary-code"}',
        "GET /auth/callback?code=canary-code&state=canary-state",
        "token id_token=canary.jwt.value access_token=canary-access refresh_token=canary-refresh",
        "a token ing_canaryAbc_123-xyz in the middle",
    ],
)
def test_redaction_removes_every_credential(line):
    assert "canary" not in redact(line)
    assert REDACTED in redact(line)


def test_redaction_keeps_ordinary_lines():
    line = "ingest_unauthorized client=10.0.0.1 route=/api/v1/ingest/health"
    assert redact(line) == line


def test_access_log_lines_for_auth_lose_their_query_string():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("10.0.0.1:5000", "GET", "/auth/callback?code=canary-code&state=canary-state", "1.1", 303),
        None,
    )

    RedactingFilter().filter(record)

    assert record.getMessage() == '10.0.0.1:5000 - "GET /auth/callback HTTP/1.1" 303'


def test_authlib_is_kept_above_debug_so_the_pkce_verifier_is_never_logged():
    install_log_redaction()

    assert logging.getLogger("authlib").getEffectiveLevel() > logging.DEBUG


def test_settings_secrets_never_reach_a_log(caplog):
    settings = TEST_SETTINGS.model_copy(update={"dev_login_key": SecretStr("canary-dev-key")})
    logging.getLogger("app").warning("settings: %s", settings)

    # SecretStr prints asterisks; the client ID and the sub are identifiers, not secrets.
    for secret in ("canary-dev-key", CLIENT_SECRET, "canary-oauth-state-secret"):
        assert secret not in caplog.text
