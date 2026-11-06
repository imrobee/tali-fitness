"""POST/GET /api/v1/sync/strava, with Airflow faked by a real local HTTP server, so the
client's actual requests (token, trigger, run state) are checked at the HTTP boundary; and
in production, with GitHub Actions faked at the HTTP boundary too (D133).

Clock frozen at Tue 2026-10-20 20:00 Manila (12:00 UTC).
"""

import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx2
import pytest
from conftest import app
from pydantic import SecretStr
from sqlalchemy import Engine, text

from app.airflow import AirflowClient, get_airflow
from app.sync import GitHubSync, get_github_sync

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


class FakeAirflow(BaseHTTPRequestHandler):
    """Answers like Airflow 3: a token, a new run, and a run's state."""

    calls: list = []
    state = "running"
    trigger_status = 200

    def _answer(self, status: int, body: dict) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_POST(self):  # noqa: N802 (the name http.server expects)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        FakeAirflow.calls.append(("POST", self.path, body, self.headers.get("Authorization")))
        if self.path == "/auth/token":
            self._answer(201, {"access_token": "fake-jwt"})
        elif FakeAirflow.trigger_status != 200:
            self._answer(FakeAirflow.trigger_status, {"detail": "nope"})
        else:
            self._answer(
                200, {"dag_run_id": "manual__2026-10-20T12:00:00+00:00", "state": "queued"}
            )

    def do_GET(self):  # noqa: N802
        FakeAirflow.calls.append(("GET", self.path, None, self.headers.get("Authorization")))
        self._answer(200, {"state": FakeAirflow.state})

    def log_message(self, *args):  # keep the test output quiet
        pass


@pytest.fixture
def airflow():
    FakeAirflow.calls = []
    FakeAirflow.state = "running"
    FakeAirflow.trigger_status = 200
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAirflow)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = AirflowClient(f"http://127.0.0.1:{server.server_port}", "admin", SecretStr("secret"))
    app.dependency_overrides[get_airflow] = lambda: client
    yield FakeAirflow
    app.dependency_overrides.pop(get_airflow, None)
    server.shutdown()


@pytest.fixture(autouse=True)
def empty_sync_requests(engine: Engine):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE ops.sync_requests"))


def add_request(engine: Engine, at: datetime, run_id: str = "manual__old") -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ops.sync_requests (source, requested_at, airflow_run_id) "
                "VALUES ('strava', :at, :id)"
            ),
            {"at": at, "id": run_id},
        )


def add_running_strava_run(engine: Engine, started: datetime) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ops.pipeline_runs (source, started_at, status) "
                "VALUES ('strava', :at, 'running')"
            ),
            {"at": started},
        )


def test_sync_now_starts_strava_sync_through_airflow(client, airflow):
    response = client.post("/api/v1/sync/strava")

    assert response.status_code == 202
    assert response.json()["state"] == "queued"
    token_call, trigger_call = airflow.calls
    assert token_call[:3] == ("POST", "/auth/token", {"username": "admin", "password": "secret"})
    assert trigger_call == (
        "POST",
        "/api/v2/dags/strava_sync/dagRuns",
        {"logical_date": None},
        "Bearer fake-jwt",
    )


def test_a_second_request_within_two_minutes_is_refused(client, engine, airflow):
    add_request(engine, NOW - timedelta(seconds=30))

    response = client.post("/api/v1/sync/strava")

    assert (response.status_code, response.json()["error"]["code"]) == (429, "sync_cooldown")
    assert airflow.calls == []  # Airflow was never asked


def test_after_the_cooldown_a_new_request_goes_through(client, engine, airflow):
    add_request(engine, NOW - timedelta(minutes=2, seconds=1))

    assert client.post("/api/v1/sync/strava").status_code == 202


def test_no_request_while_a_strava_run_is_in_progress(client, engine, airflow):
    add_running_strava_run(engine, NOW - timedelta(minutes=5))

    response = client.post("/api/v1/sync/strava")

    assert (response.status_code, response.json()["error"]["code"]) == (409, "sync_running")


def test_a_running_row_left_by_a_crash_does_not_block_forever(client, engine, airflow):
    add_running_strava_run(engine, NOW - timedelta(hours=2))

    assert client.post("/api/v1/sync/strava").status_code == 202


def test_an_airflow_error_is_a_502_and_nothing_is_recorded(client, engine, airflow):
    airflow.trigger_status = 500

    response = client.post("/api/v1/sync/strava")

    assert (response.status_code, response.json()["error"]["code"]) == (502, "airflow_unavailable")
    assert "secret" not in response.text
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM ops.sync_requests")).scalar_one() == 0


def test_the_status_follows_the_airflow_run(client, engine, airflow):
    add_request(engine, NOW - timedelta(minutes=1), run_id="manual__2026-10-20T11:59:00+00:00")
    airflow.state = "success"

    body = client.get("/api/v1/sync/strava").json()

    assert (body["dag_run_id"], body["state"]) == ("manual__2026-10-20T11:59:00+00:00", "success")
    assert (
        airflow.calls[-1][1]
        == "/api/v2/dags/strava_sync/dagRuns/manual__2026-10-20T11%3A59%3A00%2B00%3A00"
    )


def test_before_any_request_the_status_is_empty(client, airflow):
    body = client.get("/api/v1/sync/strava").json()

    assert body == {"requested_at": None, "dag_run_id": None, "state": None}


def test_without_airflow_sync_is_unavailable(client):
    app.dependency_overrides[get_airflow] = lambda: None
    try:
        response = client.post("/api/v1/sync/strava")
    finally:
        app.dependency_overrides.pop(get_airflow, None)

    assert (response.status_code, response.json()["error"]["code"]) == (503, "sync_unavailable")


# --- production: GitHub Actions instead of Airflow (D133) ------------------------------------


class FakeGitHub:
    def __init__(self, status: int = 204) -> None:
        self.status = status
        self.calls: list[httpx2.Request] = []
        self.transport = httpx2.MockTransport(self.answer)

    def answer(self, request: httpx2.Request) -> httpx2.Response:
        self.calls.append(request)
        return httpx2.Response(self.status)


@pytest.fixture
def github():
    fake = FakeGitHub()
    sync = GitHubSync("imrobee/tali-fitness", SecretStr("canary-dispatch-token"), fake.transport)
    app.dependency_overrides[get_github_sync] = lambda: sync
    app.dependency_overrides[get_airflow] = lambda: None  # production has no Airflow
    yield fake
    app.dependency_overrides.pop(get_github_sync, None)
    app.dependency_overrides.pop(get_airflow, None)


def add_strava_run(engine: Engine, started: datetime, status: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ops.pipeline_runs (source, started_at, status) "
                "VALUES ('strava', :at, :status)"
            ),
            {"at": started, "status": status},
        )


def test_in_production_sync_now_starts_the_pipeline_workflow(client, engine, github):
    response = client.post("/api/v1/sync/strava")

    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "queued" and body["dag_run_id"].startswith("github-")
    (call,) = github.calls
    assert (
        call.url.path == "/repos/imrobee/tali-fitness/actions/workflows/pipeline.yml/dispatches"
    )
    assert json.loads(call.content) == {"ref": "main", "inputs": {"job": "strava"}}
    assert call.headers["authorization"] == "Bearer canary-dispatch-token"
    assert "canary-dispatch-token" not in response.text
    with engine.connect() as conn:
        assert (
            conn.execute(text("SELECT airflow_run_id FROM ops.sync_requests")).scalar_one() is None
        )


def test_in_production_the_status_follows_the_run_row(client, engine, github):
    followed = client.post("/api/v1/sync/strava").json()["dag_run_id"]

    def status():
        return client.get("/api/v1/sync/strava").json()

    assert (status()["dag_run_id"], status()["state"]) == (followed, "queued")  # not started yet
    add_strava_run(engine, NOW + timedelta(seconds=40), "running")
    assert status()["state"] == "running"


@pytest.mark.parametrize(
    ("run_status", "shown"), [("success", "success"), ("partial", "success"), ("failed", "failed")]
)
def test_in_production_a_finished_run_ends_the_sync(client, engine, github, run_status, shown):
    client.post("/api/v1/sync/strava")
    add_strava_run(engine, NOW + timedelta(minutes=1), run_status)

    assert client.get("/api/v1/sync/strava").json()["state"] == shown


def test_an_older_run_is_not_mistaken_for_the_requested_one(client, engine, github):
    add_strava_run(engine, NOW - timedelta(minutes=50), "success")  # the last hourly run

    client.post("/api/v1/sync/strava")

    assert client.get("/api/v1/sync/strava").json()["state"] == "queued"


def test_if_github_refuses_nothing_is_recorded(client, engine, github):
    github.status = 403

    response = client.post("/api/v1/sync/strava")

    assert (response.status_code, response.json()["error"]["code"]) == (502, "github_unavailable")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM ops.sync_requests")).scalar_one() == 0


def test_sync_needs_sign_in(anonymous):
    assert anonymous.post("/api/v1/sync/strava").status_code == 401
