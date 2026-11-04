"""Logging that cannot leak a credential (docs/AUTH_SPEC.md section 10).

Every line passes a redaction filter: values after Authorization, Cookie, Set-Cookie,
client_secret, code, state, id_token, access_token and refresh_token are replaced, and so
is anything that looks like an ingest token (ing_...). Access-log lines for /auth/* lose
their query string, where Google's callback carries the code and the state.

The code already avoids logging these; this is the second layer for the day it does not.
"""

import logging
import re
import sys

REDACTED = "[redacted]"

# name=value, name: value, "name": "value" (JSON) and name value (a header line).
SECRET_NAMES = (
    "authorization",
    "cookie",
    "set-cookie",
    "client_secret",
    "code",
    "state",
    "id_token",
    "access_token",
    "refresh_token",
)
NAMES_PATTERN = "|".join(re.escape(name) for name in SECRET_NAMES)
SECRET_VALUE = re.compile(
    # The name, an optional quote, ":" or "=", then the value (with "Bearer " if present).
    rf"""(?P<name>\b(?:{NAMES_PATTERN})\b["']?\s*[:=]\s*["']?)"""
    r"""(?P<value>(?:Bearer\s+)?[^\s"'&,;}]+)""",
    re.IGNORECASE,
)
INGEST_TOKEN = re.compile(r"\bing_[A-Za-z0-9_-]+")


def redact(text: str) -> str:
    text = SECRET_VALUE.sub(lambda match: match.group("name") + REDACTED, text)
    return INGEST_TOKEN.sub(REDACTED, text)


def strip_query(path: str) -> str:
    return path.split("?", 1)[0]


class RedactingFilter(logging.Filter):
    """Rewrites each record's message in place, so every handler sees the redacted text."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn's access log: (client, method, path with query, HTTP version, status).
        if (
            record.name == "uvicorn.access"
            and isinstance(record.args, tuple)
            and len(record.args) == 5
        ):
            client, method, path, version, status = record.args
            if str(path).startswith("/auth/"):
                path = strip_query(str(path))
            record.args = (client, method, redact(str(path)), version, status)
            return True
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def install_log_redaction() -> None:
    """Our own handler for the app's loggers, and the filter on Uvicorn's handlers too."""
    redacting = RedactingFilter()
    root = logging.getLogger()
    if not any(isinstance(f, RedactingFilter) for h in root.handlers for f in h.filters):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        handler.addFilter(redacting)
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        for handler in logging.getLogger(name).handlers:
            if not any(isinstance(f, RedactingFilter) for f in handler.filters):
                handler.addFilter(redacting)
    # Authlib logs the PKCE verifier at DEBUG; keep it above that whatever the root level.
    logging.getLogger("authlib").setLevel(logging.WARNING)
