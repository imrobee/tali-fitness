"""Signing in with (a fake) Google, out, and the dev key (docs/AUTH_SPEC.md sections 5 and 12)."""

import logging
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import FAKE_GOOGLE, ORIGIN, TEST_SETTINGS, TEST_SUB
from fake_google import ACCESS_TOKEN, CLIENT_ID, EMAIL
from fastapi.testclient import TestClient
from joserfc.jwk import RSAKey
from pydantic import SecretStr
from sqlalchemy import text

from app.db import get_engine
from app.main import create_app


def sessions(engine) -> list:
    with engine.connect() as conn:
        return conn.execute(text("SELECT sub FROM app.session")).scalars().all()


def go_to_google(client: TestClient, next_path: str | None = None):
    params = {"next": next_path} if next_path else None
    return client.get("/auth/login", params=params, follow_redirects=False)


def sign_in_with_google(client: TestClient, next_path: str | None = None):
    """The whole round trip: our login, Google's page (approved), our callback."""
    code, state = FAKE_GOOGLE.approve(go_to_google(client, next_path).headers["location"])
    return client.get(
        "/auth/callback", params={"code": code, "state": state}, follow_redirects=False
    )


# --- the request to Google -----------------------------------------------------------------


def test_login_sends_the_browser_to_google_with_pkce_a_nonce_and_two_scopes(anonymous):
    response = go_to_google(anonymous)

    assert response.status_code == 302
    location = urlsplit(response.headers["location"])
    query = parse_qs(location.query)
    assert f"{location.scheme}://{location.netloc}" == "https://accounts.google.com"
    assert query["scope"] == ["openid email"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["client_id"] == [CLIENT_ID]
    assert query["state"] and query["nonce"] and query["code_challenge"]


def test_the_callback_address_comes_from_config_not_the_host_header(anonymous):
    response = anonymous.get(
        "/auth/login", headers={"Host": "evil.example"}, follow_redirects=False
    )

    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["redirect_uri"] == [f"{ORIGIN}/auth/callback"]


def test_the_login_state_cookie_is_short_lived_httponly_and_only_for_auth(anonymous):
    header = go_to_google(anonymous).headers["set-cookie"]
    flags = header.lower()  # Starlette writes this cookie's flags in lower case

    assert header.startswith("login_state=")
    assert "; httponly" in flags
    assert "max-age=600" in flags  # LOGIN_STATE_MINUTES
    assert "path=/auth" in flags
    assert "samesite=lax" in flags


# --- the callback ----------------------------------------------------------------------------


def test_the_allowed_account_gets_a_session_and_goes_home(anonymous, engine):
    response = sign_in_with_google(anonymous)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("session="))
    assert "HttpOnly" in session_cookie and "SameSite=lax" in session_cookie
    assert sessions(engine) == [TEST_SUB]
    assert anonymous.get("/auth/me").json() == {"signed_in": True}


def test_the_login_state_is_cleared_after_the_callback(anonymous):
    response = sign_in_with_google(anonymous)

    cleared = [c for c in response.headers.get_list("set-cookie") if c.startswith("login_state=")]
    assert cleared and "expires=Thu, 01 Jan 1970" in cleared[0]


def test_another_google_account_is_refused_and_its_sub_logged(anonymous, engine, caplog):
    FAKE_GOOGLE.sub = "canary-somebody-else"

    with caplog.at_level(logging.WARNING, logger="app.signin"):
        response = sign_in_with_google(anonymous)

    assert response.status_code == 403
    assert "isn't authorized" in response.text
    assert sessions(engine) == []
    assert "google_signin_denied sub=canary-somebody-else" in caplog.text
    for secret in (EMAIL, ACCESS_TOKEN, *FAKE_GOOGLE.id_tokens_issued):
        assert secret not in caplog.text and secret not in response.text


@pytest.mark.parametrize(
    "changes",
    [
        {"aud": "canary-another-app.apps.googleusercontent.com"},
        {"iss": "https://accounts.evil.example"},
        {"exp": int(time.time()) - 3600, "iat": int(time.time()) - 7200},  # expired
        {"nonce": "canary-not-the-nonce-we-sent"},
    ],
    ids=["wrong aud", "wrong iss", "expired", "wrong nonce"],
)
def test_an_id_token_that_fails_validation_is_refused(anonymous, engine, changes):
    FAKE_GOOGLE.claim_changes = changes

    response = sign_in_with_google(anonymous)

    assert response.status_code == 403
    assert sessions(engine) == []


def test_an_id_token_signed_with_another_key_is_refused(anonymous, engine):
    FAKE_GOOGLE.sign_with = RSAKey.generate_key(2048, parameters={"kid": "fake-google-key"})

    assert sign_in_with_google(anonymous).status_code == 403
    assert sessions(engine) == []


def test_no_id_token_means_no_sign_in(anonymous, engine):
    FAKE_GOOGLE.send_id_token = False

    assert sign_in_with_google(anonymous).status_code == 403
    assert sessions(engine) == []


def test_a_tampered_or_missing_state_is_refused(anonymous, engine):
    code, _state = FAKE_GOOGLE.approve(go_to_google(anonymous).headers["location"])

    forged = anonymous.get("/auth/callback", params={"code": code, "state": "canary-forged"})
    missing = anonymous.get("/auth/callback", params={"code": code})

    assert (forged.status_code, missing.status_code) == (403, 403)
    assert sessions(engine) == []


def test_a_replayed_callback_is_refused(anonymous, engine):
    code, state = FAKE_GOOGLE.approve(go_to_google(anonymous).headers["location"])
    params = {"code": code, "state": state}
    assert anonymous.get("/auth/callback", params=params, follow_redirects=False).status_code == 303

    assert anonymous.get("/auth/callback", params=params, follow_redirects=False).status_code == 403
    assert len(sessions(engine)) == 1


def test_a_pkce_verifier_mismatch_is_refused(anonymous, engine):
    code, state = FAKE_GOOGLE.approve(go_to_google(anonymous).headers["location"])
    nonce, _challenge = FAKE_GOOGLE.codes[code]
    FAKE_GOOGLE.codes[code] = (nonce, "canary-a-challenge-for-another-verifier")

    response = anonymous.get("/auth/callback", params={"code": code, "state": state})

    assert response.status_code == 403
    assert sessions(engine) == []


def test_an_error_from_google_is_refused(anonymous, engine):
    go_to_google(anonymous)

    response = anonymous.get("/auth/callback", params={"error": "access_denied"})

    assert response.status_code == 403
    assert sessions(engine) == []


@pytest.mark.parametrize(
    ("next_path", "lands_on"),
    [
        ("/nutrition?date=2026-10-19", "/nutrition?date=2026-10-19"),
        ("https://evil.example", "/"),
        ("//evil.example", "/"),
        ("/\\evil.example", "/"),
    ],
)
def test_after_sign_in_only_a_path_on_this_site_is_followed(anonymous, next_path, lands_on):
    response = sign_in_with_google(anonymous, next_path)

    assert response.headers["location"] == lands_on


# --- signed in or out ------------------------------------------------------------------------


def test_the_method_tells_the_web_app_which_sign_in_to_show(anonymous, key_mode):
    assert anonymous.get("/auth/method").json() == {"method": "google"}
    assert key_mode.get("/auth/method").json() == {"method": "key"}


def test_me_is_401_when_signed_out(anonymous):
    assert anonymous.get("/auth/me").status_code == 401


def test_logout_ends_the_session_and_the_old_cookie_stops_working(anonymous, engine):
    sign_in_with_google(anonymous)
    old_cookie = anonymous.cookies.get("session")

    response = anonymous.post("/auth/logout")

    assert response.status_code == 204
    assert sessions(engine) == []
    anonymous.cookies.set("session", old_cookie)
    assert anonymous.get("/auth/me").status_code == 401


def test_logout_needs_the_apps_origin(client):
    assert (
        client.post("/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403
    )


# --- the dev key form -----------------------------------------------------------------------

DEV_KEY = "canary-dev-login-key"


def test_there_is_no_dev_login_with_google_sign_in(anonymous):
    response = anonymous.post("/auth/dev-login", json={"key": DEV_KEY})

    assert response.status_code == 404


@pytest.fixture
def key_mode(engine, monkeypatch) -> TestClient:
    """The local dev app in key mode (APP_ENV=dev, AUTH_MODE=key)."""
    monkeypatch.setenv("APP_ENV", "dev")
    settings = TEST_SETTINGS.model_copy(
        update={"app_env": "dev", "auth_mode": "key", "dev_login_key": SecretStr(DEV_KEY)}
    )
    local = create_app(settings)
    local.dependency_overrides[get_engine] = lambda: engine
    return TestClient(local, headers={"Origin": ORIGIN})


def test_in_key_mode_the_right_key_signs_in(key_mode, engine):
    assert key_mode.get("/auth/me").status_code == 401

    assert key_mode.post("/auth/dev-login", json={"key": DEV_KEY}).status_code == 204

    assert key_mode.get("/auth/me").json() == {"signed_in": True}
    assert key_mode.get("/api/v1/dashboard").status_code == 200


def test_in_key_mode_a_wrong_key_is_401(key_mode, engine):
    assert key_mode.post("/auth/dev-login", json={"key": "canary-wrong"}).status_code == 401
    assert sessions(engine) == []


def test_in_key_mode_the_dev_key_form_checks_the_origin(key_mode):
    response = key_mode.post(
        "/auth/dev-login", json={"key": DEV_KEY}, headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == 403


def test_in_key_mode_there_is_no_google_sign_in(key_mode):
    assert key_mode.get("/auth/login", follow_redirects=False).status_code == 404
