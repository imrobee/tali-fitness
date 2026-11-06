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


@pytest.mark.parametrize(
    ("field", "name"),
    [
        ("google_client_id", "GOOGLE_CLIENT_ID"),
        ("google_client_secret", "GOOGLE_CLIENT_SECRET"),
        ("oauth_state_secret", "OAUTH_STATE_SECRET"),
    ],
)
def test_google_mode_needs_its_client_and_state_secret_even_in_dev(field, name):
    google_dev = dev(
        auth_mode="google",
        google_client_id="client-id.apps.googleusercontent.com",
        google_client_secret=SecretStr(CANARY_CLIENT_SECRET),
        oauth_state_secret=SecretStr(CANARY_STATE_SECRET),
    )
    check_startup(google_dev)  # complete: starts, even without ALLOWED_GOOGLE_SUB

    assert f"AUTH_MODE=google needs {name}" in refusal(google_dev.model_copy(update={field: None}))


@pytest.mark.parametrize("value", ["*", "10.0.0.1,*"])
def test_proxy_headers_are_never_trusted_from_everyone(value):
    assert "FORWARDED_ALLOW_IPS must list" in refusal(production(forwarded_allow_ips=value))
    check_startup(production(forwarded_allow_ips="10.0.0.1"))


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


# --- the public demo (APP_ENV=demo, DECISIONS D118) ----------------------------------------

CANARY_DEMO_URL = "postgresql+psycopg://demo_reader:canary-db-password@db.example.com:5432/app_demo"
CANARY_DEMO_SECRET = "canary-demo-session-secret-0123456789abcdef"


def demo(**changes) -> Settings:
    """A public demo config that passes every guard."""
    values = {
        "app_env": "demo",
        "auth_mode": "demo",
        "public_base_url": "https://demo.example.com",
        "warehouse_url": SecretStr(CANARY_DEMO_URL),
        "demo_session_secret": SecretStr(CANARY_DEMO_SECRET),
    }
    values.update(changes)
    return Settings(**values)


def demo_refusal(settings: Settings, environ: dict[str, str] | None = None) -> str:
    with pytest.raises(ConfigError) as caught:
        check_startup(settings, environ or {})
    message = str(caught.value)
    for canary in ("canary-db", CANARY_DEMO_SECRET, "canary-value"):
        assert canary not in message
    return message


def test_a_complete_demo_config_starts():
    check_startup(demo(), {"APP_TIMEZONE": "Asia/Manila"})


def test_the_demo_starts_locally_over_http_with_a_frozen_clock():
    check_startup(
        demo(
            public_base_url="http://localhost:5174",
            demo_session_secret=SecretStr("local-demo-session-secret-only-for-this-mac-0001"),
            now_override="2026-10-17T14:00:00+08:00",
        ),
        {},
    )


def test_the_demo_refuses_a_database_not_named_demo():
    url = CANARY_DEMO_URL.replace("/app_demo", "/app")

    assert "_demo" in demo_refusal(demo(warehouse_url=SecretStr(url)))


@pytest.mark.parametrize(
    "name",
    [
        "GOOGLE_CLIENT_SECRET",
        "OAUTH_STATE_SECRET",
        "ALLOWED_GOOGLE_SUB",
        "INGEST_TOKEN_SHA256",
        "DEV_LOGIN_KEY",
        "STRAVA_CLIENT_SECRET",
        "AIRFLOW_ADMIN_PASSWORD",
        "POSTGRES_PASSWORD",
    ],
)
def test_the_demo_refuses_to_start_holding_a_real_secret(name):
    message = demo_refusal(demo(), {name: "canary-value"})

    assert name in message


def test_an_empty_variable_does_not_count():
    check_startup(demo(), {"GOOGLE_CLIENT_SECRET": ""})


def test_the_demo_needs_a_long_session_secret():
    assert "DEMO_SESSION_SECRET" in demo_refusal(demo(demo_session_secret=SecretStr("short")))
    assert "DEMO_SESSION_SECRET" in demo_refusal(demo(demo_session_secret=None))


def test_a_public_demo_refuses_the_local_secret():
    local = SecretStr("local-demo-session-secret-only-for-this-mac-0001")

    assert "placeholder" in demo_refusal(demo(demo_session_secret=local))


def test_a_public_demo_needs_https():
    assert "https" in demo_refusal(demo(public_base_url="http://demo.example.com"))


def test_a_public_demo_refuses_a_frozen_clock():
    assert "NOW_OVERRIDE" in demo_refusal(demo(now_override="2026-10-17T14:00:00+08:00"))


def test_demo_auth_and_demo_env_go_together():
    assert "AUTH_MODE=demo" in refusal(dev(auth_mode="demo"))
    assert "AUTH_MODE=demo" in demo_refusal(demo(auth_mode="google"))


def test_the_demo_cookie_is_secure_over_https_only():
    assert demo().cookie_secure
    assert not demo(public_base_url="http://localhost:5174").cookie_secure


def test_the_demo_url_must_be_an_origin():
    assert "DEMO_PUBLIC_URL" in refusal(dev(demo_public_url="http://localhost:5174/path"))


def test_the_main_app_url_must_be_an_origin():
    assert "MAIN_APP_URL" in demo_refusal(demo(main_app_url="javascript:alert(1)"))
    assert "MAIN_APP_URL" in demo_refusal(demo(main_app_url="http://localhost:5173/path"))
