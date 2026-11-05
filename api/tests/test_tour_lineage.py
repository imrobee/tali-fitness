"""Every name the How it works page quotes exists in the code (web/src/tour/flow.json).

Its data flow names real tables, SQL functions, Airflow DAGs and tasks, and API
endpoints. A renamed table or task fails here, not in front of a recruiter. (The tour
no longer names code; test_tour_claims.py checks the facts its words state.)
"""

import json
import re
from pathlib import Path

import pytest
from conftest import TEST_SETTINGS
from sqlalchemy import text

from app.main import create_app

# The How it works page's data flow quotes names the same way (web/src/tour/flow.json).
FLOWS = json.loads(Path("/tour/flow.json").read_text())["flows"]
DAGS = "\n".join(path.read_text() for path in Path("/opt/airflow/dags").glob("*.py"))
SOURCES = {"Strava API", "iOS Shortcut (Apple Health)", "Manual entries"}
ITEMS = [
    (flow["id"], item["kind"], item["name"])
    for flow in FLOWS
    for step in flow["steps"]
    for item in step["names"]
]


def endpoints() -> set[str]:
    paths = create_app(TEST_SETTINGS).openapi()["paths"]
    return {f"{method.upper()} {path}" for path, ops in paths.items() for method in ops}


def test_there_is_something_to_check():
    assert len(ITEMS) > 10


@pytest.mark.parametrize(("step", "kind", "name"), ITEMS)
def test_the_name_exists(migrated_engine, step, kind, name):
    if kind == "source":
        assert name in SOURCES
    elif kind == "endpoint":
        assert name in endpoints()
    elif kind == "dag":
        assert f'dag_id="{name}"' in DAGS
    elif kind == "task":
        # A task is a function under @task in a DAG file.
        assert re.search(rf"@task[^\n]*\n\s+def {name}\(", DAGS)
    elif kind in ("table", "function"):
        schema, _, table = name.partition(".")
        query = (
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name"
            if kind == "table"
            else "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = :schema AND p.proname = :name"
        )
        with migrated_engine.connect() as conn:
            found = conn.execute(text(query), {"schema": schema, "name": table}).scalar_one()
        assert found > 0, f"{step}: {name}"
    else:
        pytest.fail(f"{step}: unknown kind {kind}")
