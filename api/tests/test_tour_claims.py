"""The facts the demo tour and the How it works page state in plain words are true of the
code (web/src/tour/steps.json, web/src/pages/howItWorks.json).

Neither names tables or functions, so instead of checking names this checks claims: how
often the jobs run, how many data checks there are, how often the demo is rebuilt. Change
a schedule and forget the words, and this fails.
"""

import json
import re
from pathlib import Path

STEPS = {step["id"]: step for step in json.loads(Path("/tour/steps.json").read_text())["steps"]}
DAGS = Path("/opt/airflow/dags")
RESEED = Path("/workflows/demo-reseed.yml").read_text()
PAGE = {s["id"]: s for s in json.loads(Path("/pages/howItWorks.json").read_text())["sections"]}


def words(step_id: str) -> str:
    step = STEPS[step_id]
    return f"{step['body']} {step.get('technical', '')}"


def test_strava_is_checked_every_hour():
    assert "every hour" in words("calendar")
    assert "Every hour, a scheduled job checks it" in PAGE["sources"]["text"]
    assert 'schedule="@hourly"' in (DAGS / "strava_sync.py").read_text()


def test_the_data_checks_run_every_hour():
    # "{n_checks} automatic checks", run by "a second Airflow job" (the data_quality DAG).
    assert "{n_checks} automatic checks" in words("pipeline")
    assert "Every hour, {n_checks} checks" in PAGE["monitoring"]["text"]
    assert re.search(r'schedule="\d+ \* \* \* \*"', (DAGS / "data_quality.py").read_text())


def test_each_check_is_a_sql_file():
    # n_checks in the story is len(CHECKS); there is one .sql file per check.
    from include.dq.checks import CHECKS

    assert len(CHECKS) == len(list(Path("/db/sql/dq").glob("*.sql")))


def test_the_demo_is_rebuilt_every_few_hours():
    assert "rebuilt every few hours" in words("done")
    assert "rebuilt every few hours" in PAGE["demo"]["text"]
    cron = re.search(r'cron: "(\S+) (\S+) ', RESEED)
    assert cron is not None
    assert re.fullmatch(r"\*/[1-6]", cron.group(2)), "every 1 to 6 hours is 'every few hours'"


def test_the_tour_never_names_code():
    # No chips and no type words: the tour is for a first-time visitor.
    for step in STEPS.values():
        assert "detail" not in step
        text = words(step["id"])
        assert not re.search(r"\b(raw|core|mart|ops|app)\.\w+", text), step["id"]


def test_the_tour_never_says_the_demo_users_nickname():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.demo.scenario import SCENARIOS, build

    now = datetime(2026, 10, 17, 14, tzinfo=ZoneInfo("Asia/Manila"))
    nicknames = {build(name, now).nickname for name in SCENARIOS} - {None}
    everything = json.dumps(STEPS) + json.dumps(PAGE)
    assert nicknames
    for nickname in nicknames:
        assert nickname not in everything


def test_the_stack_names_only_what_the_repo_uses():
    stack = PAGE["stack"]["text"]
    requirements = Path("/app/requirements.txt").read_text().lower()
    assert "fastapi" in requirements
    for name in ("PostgreSQL", "Airflow", "Python", "SQL", "FastAPI", "React", "TypeScript"):
        assert name in stack
    assert not re.search(r"\d+\.\d+", stack), "no version numbers"
