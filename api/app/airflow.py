"""A small client for Airflow's REST API, used only to start the strava_sync DAG.

Airflow stays the only code that calls Strava (DECISIONS D78); the API only asks Airflow
to run the DAG now. Endpoints checked against Airflow 3.3.2's own OpenAPI spec:
POST /auth/token gives a JWT (`access_token`), POST /api/v2/dags/{dag_id}/dagRuns starts
a run (`logical_date` is required and may be null), GET .../dagRuns/{dag_run_id} reads
its state. Python's urllib, so no new dependency.
"""

import json
import os
import urllib.error
import urllib.request

TIMEOUT_S = 10


class AirflowError(Exception):
    """Airflow could not be reached, or refused the request."""


class AirflowClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

    def _request(self, method: str, path: str, body: dict | None, token: str | None) -> dict:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            # Never echo the request: it can carry the password or the token.
            raise AirflowError(f"Airflow answered {error.code} for {method} {path}.") from None
        except (urllib.error.URLError, TimeoutError) as error:
            raise AirflowError(f"Airflow could not be reached ({error}).") from None

    def _token(self) -> str:
        body = {"username": self.username, "password": self.password}
        return self._request("POST", "/auth/token", body, None)["access_token"]

    def trigger(self, dag_id: str) -> str:
        """Start a run now; returns its dag_run_id."""
        run = self._request(
            "POST", f"/api/v2/dags/{dag_id}/dagRuns", {"logical_date": None}, self._token()
        )
        return run["dag_run_id"]

    def run_state(self, dag_id: str, dag_run_id: str) -> str:
        """queued, running, success or failed."""
        path = f"/api/v2/dags/{dag_id}/dagRuns/{urllib.request.quote(dag_run_id, safe='')}"
        return self._request("GET", path, None, self._token())["state"]


def get_airflow() -> AirflowClient | None:
    """The client, or None where Airflow is not part of the stack (the demo)."""
    url = os.environ.get("AIRFLOW_URL")
    user = os.environ.get("AIRFLOW_ADMIN_USER")
    password = os.environ.get("AIRFLOW_ADMIN_PASSWORD")
    if not (url and user and password):
        return None
    return AirflowClient(url, user, password)
