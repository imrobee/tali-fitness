"""Startup guards (docs/AUTH_SPEC.md section 4): one test per guard.

Secrets here are obvious fake canaries; every refusal is also checked for not echoing them.
"""

import pytest
from pydantic import SecretStr

from app.config import ConfigError, Settings, check_startup, load_settings
from app.main import create_app

CANARY_STATE_SECRET = "canary-oauth-state-secret-0123456789abcdef"
CANARY_CLIENT_SECRET = "canary-google-client-secret"
CANARY_DEV_KEY = "canary-dev-login-key"
CANARY_DB_URL = "postgresql+psycopg://fitness:canary-db-password@postgres:5432/app"
HASH = "a" * 64


def production(**changes) -> Settings:
    """A production config that passes every guard; each test breaks one thing."""
    values = {
        "app_env": "production",
        "auth_mode": "google",
        "public_base_url": "https://tracker.example.com",
        "warehouse_url": SecretStr(CANARY_DB_URL),
        "google_client_id": "client-id.apps.googleusercontent.com",
        "google_client_secret": SecretStr(CANARY_CLIENT_SECRET),
        "oauth_state_secret": SecretStr(CANARY_STATE_SECRET),
        "allowed_google_sub": "123456789",
        "ingest_token_sha256": SecretStr(HASH),
    }
    values.update(changes)
    return Settings(**values)


def dev(**changes) -> Settings:
    values = {
        "app_env": "dev",
        "auth_mode": "key",
        "public_base_url": "http://localhost:5173",
        "warehouse_url": SecretStr(CANARY_DB_URL),
        "dev_login_key": SecretStr(CANARY_DEV_KEY),
    }
    values.update(changes)
    return Settings(**values)


def refusal(settings: Settings) -> str:
    with pytest.raises(ConfigError) as caught:
        check_startup(settings)
    message = str(caught.value)
    for canary in (CANARY_STATE_SECRET, CANARY_CLIENT_SECRET, CANARY_DEV_KEY, "canary-db"):
        assert canary not in message
    return message


def test_a_complete_production_config_starts():
    check_startup(production())


def test_a_local_dev_config_starts():
    check_startup(dev())
    check_startup(dev(public_base_url="http://192.168.100.127:5173"))  # the iPhone on the LAN
    check_startup(dev(public_base_url="http://web-demo:5173"))  # a Compose service name


def test_production_needs_google_sign_in():
    assert "AUTH_MODE must be google" in refusal(production(auth_mode="key"))


def test_production_needs_https():
    assert "https://" in refusal(production(public_base_url="http://tracker.example.com"))


@pytest.mark.parametrize(
    ("field", "name"),
    [
        ("google_client_id", "GOOGLE_CLIENT_ID"),
        ("google_client_secret", "GOOGLE_CLIENT_SECRET"),
        ("allowed_google_sub", "ALLOWED_GOOGLE_SUB"),
        ("oauth_state_secret", "OAUTH_STATE_SECRET"),
        ("ingest_token_sha256", "INGEST_TOKEN_SHA256"),
    ],
)
def test_production_needs_every_credential(field, name):
    assert f"{name} must be set" in refusal(production(**{field: None}))


def test_production_refuses_a_short_state_secret():
    message = refusal(production(oauth_state_secret=SecretStr("too-short")))
    assert "OAUTH_STATE_SECRET must be at least 32 bytes" in message


def test_production_refuses_a_placeholder_state_secret():
    assert "OAUTH_STATE_SECRET" in refusal(production(oauth_state_secret=SecretStr("change-me")))


def test_the_ingest_hash_must_be_64_hex_characters():
    assert "INGEST_TOKEN_SHA256 must be 64" in refusal(
        production(ingest_token_sha256=SecretStr("ing_not-a-hash"))
    )
    assert "INGEST_TOKEN_SHA256_NEXT must be 64" in refusal(
        dev(ingest_token_sha256_next=SecretStr("A" * 64))
    )


def test_production_refuses_a_dev_login_key():
    message = refusal(production(dev_login_key=SecretStr(CANARY_DEV_KEY)))
    assert "DEV_LOGIN_KEY must be unset" in message


def test_production_refuses_a_frozen_clock():
    message = refusal(production(now_override="2026-10-17T14:00:00+08:00"))
    assert "NOW_OVERRIDE must be unset" in message


def test_production_cookies_are_secure():
    assert production().cookie_secure
    assert not dev().cookie_secure


def test_key_mode_is_dev_only():
    assert "AUTH_MODE=key is allowed only when APP_ENV=dev" in refusal(dev(app_env="test"))


def test_key_mode_needs_a_dev_login_key():
    assert "AUTH_MODE=key needs DEV_LOGIN_KEY" in refusal(dev(dev_login_key=None))


@pytest.mark.parametrize(
    "url", ["https://tracker.example.com", "http://tracker.fly.dev", "http://8.8.8.8:5173"]
)
def test_dev_refuses_a_public_address(url):
    # dev relaxes the guards, so a deployed dev config must not start.
    assert "APP_ENV=dev is local only" in refusal(dev(public_base_url=url))


@pytest.mark.parametrize(
    "url", ["localhost:5173", "ftp://localhost", "http://localhost:5173/app", "http://?x"]
)
def test_the_public_base_url_must_be_an_origin(url):
    assert "PUBLIC_BASE_URL must be http(s)://host[:port]" in refusal(dev(public_base_url=url))


def test_the_app_refuses_to_build_with_a_bad_config():
    with pytest.raises(ConfigError):
        create_app(production(auth_mode="key"))


def test_load_settings_names_bad_variables_without_their_values(monkeypatch):
    monkeypatch.setenv("APP_ENV", "canary-not-an-env")
    monkeypatch.setenv("AUTH_MODE", "google")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:5173")
    with pytest.raises(ConfigError) as caught:
        load_settings()
    assert "APP_ENV" in str(caught.value)
    assert "canary" not in str(caught.value)


def test_load_settings_treats_an_empty_variable_as_unset(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("AUTH_MODE", "key")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:5173")
    monkeypatch.setenv("NOW_OVERRIDE", "")
    assert load_settings().now_override is None


def test_secrets_never_show_in_the_settings_repr():
    shown = repr(production(dev_login_key=SecretStr(CANARY_DEV_KEY)))
    for canary in (CANARY_STATE_SECRET, CANARY_CLIENT_SECRET, CANARY_DEV_KEY, "canary-db"):
        assert canary not in shown
