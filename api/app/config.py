"""Settings from the environment, and the startup guards (docs/AUTH_SPEC.md section 4).

Every secret is a SecretStr: printing or logging the settings shows "**********", and
the real value is read only where it is used, with .get_secret_value().

The guards make the app refuse to start with a bad configuration. Their errors name the
variable, never its value.
"""

import ipaddress
import os
import re
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Request
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError
from sqlalchemy.engine import make_url

# Session and login lifetimes (AUTH_SPEC.md sections 4 and 6).
SESSION_ABSOLUTE_DAYS = 60
SESSION_IDLE_DAYS = 30
LOGIN_STATE_MINUTES = 10

# Values from .env.example and docker-compose.yml that must never reach production.
LOCAL_DEMO_SESSION_SECRET = "local-demo-session-secret-only-for-this-mac-0001"
PLACEHOLDERS = {"change-me", "changemelocal", LOCAL_DEMO_SESSION_SECRET}

# The demo service (APP_ENV=demo) must start with none of these: no way to sign in as Rob,
# no ingest, no Strava, no Airflow. Checked by name prefix against the whole environment,
# so a variable this file does not even read still counts (DECISIONS D118).
DEMO_FORBIDDEN_PREFIXES = (
    "GOOGLE_",
    "OAUTH_",
    "ALLOWED_GOOGLE_",
    "INGEST_TOKEN",
    "DEV_LOGIN_KEY",
    "STRAVA_",
    "AIRFLOW_",
    "POSTGRES_",
    # The demo's rebuild credentials: only the reseed job and the local setup hold them.
    "DEMO_SEED_URL",
    "DEMO_ADMIN_URL",
)
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class ConfigError(Exception):
    """The configuration is unsafe or incomplete; the message names variables only."""


class Settings(BaseModel):
    # frozen: settings cannot be changed by accident after startup.
    model_config = ConfigDict(frozen=True)

    app_env: Literal["dev", "test", "production", "demo"]
    auth_mode: Literal["google", "key", "demo"]
    public_base_url: str
    warehouse_url: SecretStr
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    oauth_state_secret: SecretStr | None = None
    allowed_google_sub: str | None = None
    # Hashes, not secrets, but kept out of logs like one.
    ingest_token_sha256: SecretStr | None = None
    ingest_token_sha256_next: SecretStr | None = None
    dev_login_key: SecretStr | None = None
    now_override: str | None = None
    airflow_url: str | None = None
    airflow_admin_user: str | None = None
    airflow_admin_password: SecretStr | None = None
    # The demo service: signs its visitors' cookies. The real service: where its Demo
    # button sends people.
    demo_session_secret: SecretStr | None = None
    demo_public_url: str | None = None
    # The demo service: may ask GitHub Actions to rebuild stale demo data (D121). A
    # fine-grained token with Actions: write on this one repository, nothing else.
    demo_reseed_token: SecretStr | None = None
    demo_reseed_repo: str | None = None
    # Read by Uvicorn itself; here only so the guards can check it.
    forwarded_allow_ips: str | None = None

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies are sent only over HTTPS: always on in production, and on the
        demo service whenever it is served over HTTPS."""
        if self.app_env == "demo":
            return self.public_base_url.startswith("https://")
        return self.app_env == "production"

    @property
    def public_origin(self) -> str:
        """scheme://host[:port] of PUBLIC_BASE_URL, what a browser sends as Origin."""
        parts = urlsplit(self.public_base_url)
        return f"{parts.scheme}://{parts.netloc}"


# Environment variable name -> Settings field. One list, so names are easy to search.
ENV_NAMES = {
    "APP_ENV": "app_env",
    "AUTH_MODE": "auth_mode",
    "PUBLIC_BASE_URL": "public_base_url",
    "WAREHOUSE_URL": "warehouse_url",
    "GOOGLE_CLIENT_ID": "google_client_id",
    "GOOGLE_CLIENT_SECRET": "google_client_secret",
    "OAUTH_STATE_SECRET": "oauth_state_secret",
    "ALLOWED_GOOGLE_SUB": "allowed_google_sub",
    "INGEST_TOKEN_SHA256": "ingest_token_sha256",
    "INGEST_TOKEN_SHA256_NEXT": "ingest_token_sha256_next",
    "DEV_LOGIN_KEY": "dev_login_key",
    "NOW_OVERRIDE": "now_override",
    "AIRFLOW_URL": "airflow_url",
    "AIRFLOW_ADMIN_USER": "airflow_admin_user",
    "AIRFLOW_ADMIN_PASSWORD": "airflow_admin_password",
    "FORWARDED_ALLOW_IPS": "forwarded_allow_ips",
    "DEMO_SESSION_SECRET": "demo_session_secret",
    "DEMO_PUBLIC_URL": "demo_public_url",
    "DEMO_RESEED_TOKEN": "demo_reseed_token",
    "DEMO_RESEED_REPO": "demo_reseed_repo",
}


def load_settings() -> Settings:
    """Read the environment. An empty variable (NOW_OVERRIDE=) counts as unset."""
    values = {}
    for env_name, field in ENV_NAMES.items():
        value = os.environ.get(env_name, "").strip()
        if value:
            values[field] = value
    try:
        return Settings(**values)
    except ValidationError as error:
        # Pydantic's own message includes the rejected input, which could be a secret,
        # so report only which variables are wrong.
        fields = {str(problem["loc"][0]) for problem in error.errors()}
        names = sorted(name for name, field in ENV_NAMES.items() if field in fields)
        raise ConfigError(f"Missing or invalid: {', '.join(names)}.") from None


def get_settings(request: Request) -> Settings:
    """FastAPI dependency: the settings create_app() checked and stored on the app."""
    return request.app.state.settings


def check_startup(settings: Settings, environ: dict[str, str] | None = None) -> None:
    """Raise ConfigError listing every problem, or return if the config is safe.

    environ is the process environment (tests pass their own): the demo guard checks
    variable names there, including ones Settings never reads."""
    problems = _problems_everywhere(settings)
    if settings.app_env == "production":
        problems += _problems_in_production(settings)
    if settings.app_env == "demo":
        problems += _problems_in_demo(settings, os.environ if environ is None else environ)
    if problems:
        raise ConfigError("Refusing to start: " + " ".join(problems))


def _problems_everywhere(settings: Settings) -> list[str]:
    problems = []
    if not _is_origin_url(settings.public_base_url):
        problems.append("PUBLIC_BASE_URL must be http(s)://host[:port] with no path.")
    if settings.auth_mode == "key" and settings.app_env != "dev":
        problems.append("AUTH_MODE=key is allowed only when APP_ENV=dev.")
    if (settings.auth_mode == "demo") != (settings.app_env == "demo"):
        problems.append("AUTH_MODE=demo and APP_ENV=demo go together.")
    if settings.demo_public_url is not None and not _is_origin_url(settings.demo_public_url):
        problems.append("DEMO_PUBLIC_URL must be http(s)://host[:port] with no path.")
    if settings.auth_mode == "key" and settings.dev_login_key is None:
        problems.append("AUTH_MODE=key needs DEV_LOGIN_KEY.")
    if settings.auth_mode == "google":
        # Sign-in cannot work without these, in any environment. ALLOWED_GOOGLE_SUB may
        # be empty in dev: the first (denied) sign-in logs the sub to put there.
        google = {
            "GOOGLE_CLIENT_ID": settings.google_client_id,
            "GOOGLE_CLIENT_SECRET": settings.google_client_secret,
            "OAUTH_STATE_SECRET": settings.oauth_state_secret,
        }
        for name, value in google.items():
            if value is None:
                problems.append(f"AUTH_MODE=google needs {name}.")
    # dev relaxes the guards (plain cookies, docs, key login), so it must stay on this
    # machine or the LAN: a public address means someone is deploying it.
    # Uvicorn takes the client IP and scheme from X-Forwarded-* only from these addresses;
    # "*" would let anyone claim any IP (and dodge the rate limits).
    if settings.forwarded_allow_ips and "*" in settings.forwarded_allow_ips.split(","):
        problems.append("FORWARDED_ALLOW_IPS must list the proxy's address, never *.")
    if settings.app_env == "dev" and not _is_local_url(settings.public_base_url):
        problems.append("APP_ENV=dev is local only: PUBLIC_BASE_URL must be a local address.")
    for name, value in (
        ("INGEST_TOKEN_SHA256", settings.ingest_token_sha256),
        ("INGEST_TOKEN_SHA256_NEXT", settings.ingest_token_sha256_next),
    ):
        if value is not None and not SHA256_HEX.fullmatch(value.get_secret_value()):
            problems.append(f"{name} must be 64 lowercase hex characters.")
    return problems


def _problems_in_production(settings: Settings) -> list[str]:
    problems = []
    if settings.auth_mode != "google":
        problems.append("AUTH_MODE must be google in production.")
    if not settings.public_base_url.startswith("https://"):
        problems.append("PUBLIC_BASE_URL must start with https:// in production.")
    required = {
        "GOOGLE_CLIENT_ID": settings.google_client_id,
        "GOOGLE_CLIENT_SECRET": settings.google_client_secret,
        "ALLOWED_GOOGLE_SUB": settings.allowed_google_sub,
        "OAUTH_STATE_SECRET": settings.oauth_state_secret,
        "INGEST_TOKEN_SHA256": settings.ingest_token_sha256,
    }
    for name, value in required.items():
        if value is None:
            problems.append(f"{name} must be set in production.")
    state_secret = settings.oauth_state_secret
    if state_secret is not None:
        raw = state_secret.get_secret_value()
        if len(raw.encode()) < 32 or raw in PLACEHOLDERS:
            problems.append("OAUTH_STATE_SECRET must be at least 32 bytes and not a placeholder.")
    if settings.dev_login_key is not None:
        problems.append("DEV_LOGIN_KEY must be unset in production.")
    if settings.now_override is not None:
        problems.append("NOW_OVERRIDE must be unset in production.")
    if not settings.cookie_secure:
        problems.append("Cookies must be Secure in production.")
    return problems


def _problems_in_demo(settings: Settings, environ: dict[str, str]) -> list[str]:
    """The public demo can reach only its own synthetic database, and holds no secret of
    the real app (docs/ARCHITECTURE.md section 13)."""
    problems = []
    database = make_url(settings.warehouse_url.get_secret_value()).database or ""
    if not database.endswith("_demo"):
        problems.append("APP_ENV=demo needs a WAREHOUSE_URL database whose name ends in _demo.")
    present = sorted(
        name for name in environ if environ[name] and name.startswith(DEMO_FORBIDDEN_PREFIXES)
    )
    if present:
        problems.append(f"APP_ENV=demo must not have: {', '.join(present)}.")
    secret = settings.demo_session_secret
    if secret is None or len(secret.get_secret_value().encode()) < 32:
        problems.append("APP_ENV=demo needs a DEMO_SESSION_SECRET of at least 32 bytes.")
    elif settings.cookie_secure and secret.get_secret_value() in PLACEHOLDERS:
        problems.append("DEMO_SESSION_SECRET is the local placeholder: set a real one.")
    local = _is_local_url(settings.public_base_url)
    if not local and not settings.public_base_url.startswith("https://"):
        problems.append("PUBLIC_BASE_URL must start with https:// for a public demo.")
    if not local and settings.now_override is not None:
        problems.append("NOW_OVERRIDE is for local screenshots only, not a public demo.")
    if settings.demo_reseed_token is not None and not REPO.fullmatch(
        settings.demo_reseed_repo or ""
    ):
        problems.append("DEMO_RESEED_TOKEN needs DEMO_RESEED_REPO as owner/name.")
    return problems


def _is_origin_url(url: str) -> bool:
    parts = urlsplit(url)
    return (
        parts.scheme in ("http", "https")
        and bool(parts.hostname)
        and parts.path in ("", "/")
        and not parts.query
        and not parts.fragment
    )


def _is_local_url(url: str) -> bool:
    """localhost, a loopback or private IP (the LAN), or a one-word Compose service name."""
    host = urlsplit(url).hostname or ""
    if host == "localhost" or "." not in host:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False  # a dotted name like app.example.com is public
    return address.is_loopback or address.is_private
