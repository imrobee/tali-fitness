"""The public demo cannot reach real data, and cannot change anything (DECISIONS D118).

A real demo database is built here the way `seed_demo.py setup` builds it: its own two
roles, the real test database locked against them. The demo app runs on the read-only
role only, exactly as the demo service does.
"""

import json
import os

import httpx2
import pytest
from conftest import TEST_SETTINGS, sign_in
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.config import Settings
from app.db import get_engine
from app.demo import session as demo_session
from app.demo.session import new_demo_cookie
from app.demo.setup import DemoRoles, prepare_demo_database
from app.main import create_app
from app.security import RateLimiter

DEMO_DATABASE = "apitest_demo"
# Test-only roles, so the tests never change the local demo stack's own roles.
ROLES = DemoRoles(
    reader="test_demo_reader",
    reader_password="canaryreader0001",
    writer="test_demo_writer",
    writer_password="canarywriter0001",
)
DEMO_ORIGIN = "http://testserver"
DEMO_SECRET = "canary-demo-session-secret-0123456789abcdef"


def server_url():
    return make_url(os.environ["WAREHOUSE_URL"])


def reader_url(database: str = DEMO_DATABASE):
    return server_url().set(
        database=database, username=ROLES.reader, password=ROLES.reader_password
    )


def writer_url(database: str = DEMO_DATABASE):
    return server_url().set(
        database=database, username=ROLES.writer, password=ROLES.writer_password
    )


DEMO_SETTINGS = Settings(
    app_env="demo",
    auth_mode="demo",
    public_base_url=DEMO_ORIGIN,
    warehouse_url=SecretStr(reader_url().render_as_string(hide_password=False)),
    demo_session_secret=SecretStr(DEMO_SECRET),
    main_app_url="http://localhost:5173",
)
# environ={}: the guard checks this, not the test container's own environment (.env).
demo_app = create_app(DEMO_SETTINGS, environ={})


@pytest.fixture(scope="module")
def demo_database(migrated_engine: Engine):
    """apitest_demo, built by the real setup code, with the real test database locked."""
    real_database = migrated_engine.url.database
    admin = create_engine(
        server_url().set(database="postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True
    )
    prepare_demo_database(admin, DEMO_DATABASE, ROLES, lock=[real_database])
    writer = create_engine(writer_url())
    reader = create_engine(reader_url())
    yield {"writer": writer, "reader": reader, "real_database": real_database}

    writer.dispose()
    reader.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {DEMO_DATABASE} WITH (FORCE)"))
        conn.execute(text(f"DROP ROLE IF EXISTS {ROLES.reader}"))
        conn.execute(text(f"DROP ROLE IF EXISTS {ROLES.writer}"))
    admin.dispose()


@pytest.fixture
def visitor_client(demo_database, monkeypatch) -> TestClient:
    """A browser on the demo, before it has started a visit."""
    monkeypatch.setenv("NOW_OVERRIDE", "2026-10-20T20:00:00+08:00")
    demo_app.state.rate_limiter = RateLimiter()
    demo_app.dependency_overrides[get_engine] = lambda: demo_database["reader"]
    yield TestClient(demo_app, headers={"Origin": DEMO_ORIGIN})
    demo_app.dependency_overrides.clear()


@pytest.fixture
def visitor(visitor_client: TestClient) -> TestClient:
    """The same browser after pressing Demo."""
    assert visitor_client.post("/auth/demo").status_code == 204
    return visitor_client


def demo_routes(method_filter) -> list[tuple[str, str]]:
    paths = demo_app.openapi()["paths"]
    return sorted(
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
        if method_filter(method.upper())
    )


def real_routes() -> list[tuple[str, str]]:
    paths = create_app(TEST_SETTINGS).openapi()["paths"]
    return sorted(
        (method.upper(), path) for path, operations in paths.items() for method in operations
    )


def fill(path: str) -> str:
    return path.replace("{day}", "2026-10-20").replace("{activity_id}", "1")


# --- the demo visit --------------------------------------------------------------------


def test_the_demo_says_what_it_is(visitor_client):
    assert visitor_client.get("/auth/method").json()["method"] == "demo"


def test_nothing_opens_before_the_visit_starts(visitor_client):
    assert visitor_client.get("/api/v1/dashboard").status_code == 401
    assert visitor_client.get("/auth/me").status_code == 401


def test_a_visit_reads_the_demo(visitor):
    assert visitor.get("/auth/me").json() == {
        "signed_in": True,
        "demo": True,
        "story": None,
        "launch_url": "http://localhost:5173",  # the real app's launch screen
    }
    assert visitor.get("/api/v1/dashboard").status_code == 200


@pytest.mark.parametrize(("method", "path"), demo_routes(lambda method: method == "GET"))
def test_every_read_works_on_the_read_only_role(visitor, method, path):
    # A 500 here would mean a page tries to write (the role refuses) or reads a table it
    # was not granted. 404 is fine: activity 1 does not exist in an empty demo.
    response = visitor.get(fill(path))

    assert response.status_code in (200, 404), f"{path}: {response.status_code}"


def test_a_forged_cookie_is_refused(visitor_client):
    forged = new_demo_cookie(DEMO_SETTINGS)[:-2] + "xx"
    visitor_client.cookies.set("demo_session", forged)

    assert visitor_client.get("/api/v1/dashboard").status_code == 401


def test_a_cookie_signed_with_another_secret_is_refused(visitor_client):
    other = DEMO_SETTINGS.model_copy(update={"demo_session_secret": SecretStr("x" * 40)})
    visitor_client.cookies.set("demo_session", new_demo_cookie(other))

    assert visitor_client.get("/api/v1/dashboard").status_code == 401


def test_an_expired_visit_is_refused(visitor, monkeypatch):
    monkeypatch.setattr(demo_session, "MAX_AGE", -1)

    assert visitor.get("/api/v1/dashboard").status_code == 401


def test_leaving_the_demo_clears_the_cookie(visitor):
    assert visitor.post("/auth/logout").status_code == 204
    assert visitor.get("/api/v1/dashboard").status_code == 401


# --- read-only, enforced on the server --------------------------------------------------

WRITES = [
    route
    for route in real_routes()
    if route[0] not in ("GET", "HEAD", "OPTIONS") and route[1] != "/auth/logout"
]


def test_the_write_list_covers_the_app():
    assert ("PUT", "/api/v1/me") in WRITES
    assert ("POST", "/api/v1/recovery") in WRITES
    assert ("POST", "/api/v1/ingest/health") in WRITES
    assert ("POST", "/api/v1/sync/strava") in WRITES


@pytest.mark.parametrize(("method", "path"), WRITES)
def test_every_write_of_the_real_app_is_refused(visitor, method, path):
    response = visitor.request(method, fill(path), json={})

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "demo_read_only",
        "message": "Demo mode: changes aren't saved.",
    }


def test_the_sync_and_sign_in_routes_do_not_exist(visitor):
    assert visitor.get("/api/v1/sync/strava").status_code == 404
    assert visitor.get("/auth/login").status_code == 404
    assert visitor.get("/auth/callback").status_code == 404


def test_the_database_role_refuses_writes_too(demo_database):
    """Defence in depth: even a route that forgot the rule could not write."""
    with pytest.raises(ProgrammingError, match="permission denied"):
        with demo_database["reader"].begin() as conn:
            conn.execute(text("UPDATE app.profile SET nickname = 'x'"))


@pytest.mark.parametrize("table", ["ops.oauth_tokens", "app.session"])
def test_the_reader_cannot_see_token_or_session_tables(demo_database, table):
    with pytest.raises(ProgrammingError, match="permission denied"):
        with demo_database["reader"].connect() as conn:
            conn.execute(text(f"SELECT count(*) FROM {table}"))


# --- the real data stays out of reach ----------------------------------------------------


@pytest.mark.parametrize("url_for", [reader_url, writer_url])
def test_the_demo_roles_cannot_open_the_real_database(demo_database, url_for):
    engine = create_engine(url_for(demo_database["real_database"]))
    with pytest.raises(OperationalError, match="permission denied for database"):
        engine.connect()
    engine.dispose()


def test_a_demo_cookie_opens_nothing_on_the_real_app(anonymous):
    cookie = new_demo_cookie(DEMO_SETTINGS)
    anonymous.cookies.set("demo_session", cookie)
    anonymous.cookies.set("session", cookie)

    assert anonymous.get("/api/v1/dashboard").status_code == 401


def test_a_real_session_opens_nothing_on_the_demo(visitor_client, engine):
    sign_in(visitor_client, engine)

    assert visitor_client.get("/api/v1/dashboard").status_code == 401


def test_a_real_session_still_works_on_the_real_app(client):
    assert client.get("/api/v1/dashboard").status_code == 200


def test_the_real_app_points_its_demo_button_at_the_demo(anonymous, monkeypatch):
    app = create_app(TEST_SETTINGS.model_copy(update={"demo_public_url": "http://localhost:5174"}))
    response = TestClient(app).get("/auth/method").json()

    assert response == {"method": "google", "demo_url": "http://localhost:5174"}


# --- limits on a public URL -----------------------------------------------------------


def test_starting_visits_is_rate_limited(visitor_client):
    codes = [visitor_client.post("/auth/demo").status_code for _ in range(11)]

    assert codes[:10] == [204] * 10
    assert codes[10] == 429


def test_reading_is_rate_limited(visitor):
    codes = [visitor.get("/api/v1/health").status_code for _ in range(121)]

    assert codes.count(429) == 1


def test_a_large_body_is_refused(visitor_client):
    response = visitor_client.post("/auth/demo", content=b"x" * 2048)

    assert response.status_code == 413


# --- setup never prints a password --------------------------------------------------------


def test_a_failed_role_statement_does_not_show_the_password(demo_database, capsys):
    from app.demo.setup import run_built

    engine = create_engine(writer_url(), hide_parameters=True)  # may not create roles
    with pytest.raises(RuntimeError) as caught, engine.connect() as conn:
        run_built(conn, "demo/role_create.sql", {"role": "x_demo", "password": "canarypw0042"})
    engine.dispose()

    assert "canarypw0042" not in str(caught.value)
    assert "canarypw0042" not in capsys.readouterr().err
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


# --- demo_reader can change nothing, anywhere -----------------------------------------------


def demo_tables(demo_database) -> list[str]:
    with demo_database["writer"].connect() as conn:
        return conn.execute(
            text(
                "SELECT table_schema || '.' || table_name FROM information_schema.tables "
                "WHERE table_schema IN ('raw', 'core', 'ops', 'app', 'demo') "
                "AND table_type = 'BASE TABLE' ORDER BY 1"
            )
        ).scalars().all()  # fmt: skip


@pytest.mark.parametrize("statement", ["DELETE FROM {}", "UPDATE {} SET {} = {}", "TRUNCATE {}"])
def test_the_reader_can_change_no_demo_table(demo_database, statement):
    tables = demo_tables(demo_database)
    assert len(tables) > 20
    refused = 0
    for table in tables:
        with demo_database["writer"].connect() as conn:
            column = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema || '.' || table_name = :t "
                    # an ordinary column: an identity one is refused before privileges are
                    "AND is_identity = 'NO' AND is_generated = 'NEVER' "
                    "ORDER BY ordinal_position"
                ),
                {"t": table},
            ).scalars().first()  # fmt: skip
        sql = statement.format(table, column, column)
        with pytest.raises(ProgrammingError, match="permission denied"):
            with demo_database["reader"].begin() as conn:
                conn.execute(text(sql))
        refused += 1
    assert refused == len(tables)


# --- the demo's own credentials can't reach the demo service either --------------------------


def test_the_demo_service_refuses_to_start_with_the_seed_credential():
    from app.config import ConfigError, check_startup

    with pytest.raises(ConfigError, match="DEMO_SEED_URL"):
        check_startup(DEMO_SETTINGS, {"DEMO_SEED_URL": "postgresql://demo_seed:x@db/app_demo"})


# --- self-heal: a stale demo asks GitHub Actions for a rebuild (D121) ----------------------


class FakeGitHub:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list = []
        self.fail = fail
        self.transport = httpx2.MockTransport(self.answer)

    def answer(self, request):
        self.calls.append(request)
        if self.fail:
            raise httpx2.ConnectError("GitHub is down")
        return httpx2.Response(200, json={"workflow_run_id": 1})


def healing_client(demo_database, github: FakeGitHub, token: bool = True) -> TestClient:
    settings = DEMO_SETTINGS.model_copy(
        update={
            "demo_reseed_token": SecretStr("canary-github-token-0001") if token else None,
            "demo_reseed_repo": "imrobee/fitness-tracker",
        }
    )
    app = create_app(settings, environ={}, github_transport=github.transport)
    app.dependency_overrides[get_engine] = lambda: demo_database["reader"]
    return TestClient(app)


def set_seeded(demo_database, hours_ago: float | None) -> None:
    with demo_database["writer"].begin() as conn:
        conn.execute(text("DELETE FROM demo.seed_state"))
        if hours_ago is not None:
            conn.execute(
                text(
                    "INSERT INTO demo.seed_state VALUES (1, 'midweek', now(), "
                    "now() - make_interval(secs => :s), 4000)"
                ),
                {"s": hours_ago * 3600},
            )


def test_a_stale_demo_asks_github_once_and_the_visitor_never_waits(demo_database, caplog):
    set_seeded(demo_database, hours_ago=30)
    github = FakeGitHub()
    client = healing_client(demo_database, github)

    assert client.post("/auth/demo").status_code == 204
    assert client.post("/auth/demo").status_code == 204  # within 30 minutes: not again

    assert len(github.calls) == 1
    call = github.calls[0]
    assert call.method == "POST"
    assert str(call.url) == (
        "https://api.github.com/repos/imrobee/fitness-tracker/actions/workflows/"
        "demo-reseed.yml/dispatches"
    )
    assert json.loads(call.content) == {"ref": "main"}
    assert call.headers["X-GitHub-Api-Version"] == "2026-03-10"
    assert "canary-github-token" not in caplog.text


def test_fresh_data_asks_for_nothing(demo_database):
    set_seeded(demo_database, hours_ago=2)
    github = FakeGitHub()

    healing_client(demo_database, github).post("/auth/demo")

    assert github.calls == []


def test_without_a_token_nothing_is_asked(demo_database):
    set_seeded(demo_database, hours_ago=None)
    github = FakeGitHub()

    healing_client(demo_database, github, token=False).post("/auth/demo")

    assert github.calls == []


def test_github_being_down_does_not_stop_the_visit(demo_database):
    set_seeded(demo_database, hours_ago=None)
    github = FakeGitHub(fail=True)
    client = healing_client(demo_database, github)

    assert client.post("/auth/demo").status_code == 204
    assert client.get("/api/v1/dashboard").status_code == 200
    assert len(github.calls) == 1
