"""vercel.json (DECISIONS D131): the static site sends the same security headers as the API
(docs/AUTH_SPEC.md section 10), and requests reach the right service."""

import json
import tomllib
from pathlib import Path

from app.security import HSTS, SECURITY_HEADERS

CONFIG = json.loads(Path("/vercel.json").read_text())


def web_headers() -> dict[str, str]:
    (rule,) = CONFIG["services"]["web"]["headers"]
    assert rule["source"] == "/(.*)"
    return {header["key"]: header["value"] for header in rule["headers"]}


def test_the_static_site_sends_the_apis_security_headers():
    expected = {key: value for key, value in SECURITY_HEADERS.items() if key != "Cache-Control"}
    # Cache-Control: no-store is for signed-in data; the built files may be cached.
    assert web_headers() == {**expected, "Strict-Transport-Security": HSTS}


def test_api_and_auth_go_to_python_and_everything_else_to_the_spa():
    routes = [(rule["source"], rule["destination"]["service"]) for rule in CONFIG["rewrites"]]

    assert routes == [("/api/(.*)", "api"), ("/auth/(.*)", "api"), ("/(.*)", "web")]
    assert CONFIG["services"]["api"]["entrypoint"] == "vercel_api:app"


def test_the_spa_answers_its_own_routes():
    assert {"source": "/(.*)", "destination": "/index.html"} in CONFIG["services"]["web"][
        "rewrites"
    ]


def test_vercel_installs_the_same_dependencies_as_docker():
    # Vercel installs from the root pyproject.toml; Docker from api/requirements.txt.
    project = tomllib.loads(Path("/pyproject.toml").read_text())["project"]
    requirements = [
        line.strip()
        for line in Path("/app/requirements.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

    assert project["dependencies"] == requirements
    assert project["requires-python"] == "==3.13.*"
