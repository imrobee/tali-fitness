"""The demo's data comes out of the real pipeline, the same every time (DECISIONS D119).

A demo database is built the way `make seed-demo` builds it, a scenario is replayed
through the real ingest, sync, parse and data-quality code, and the numbers the pages
show are read back through the demo API on its read-only role.
"""

import os
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db import get_engine
from app.demo.replay import replay
from app.demo.scenario import TZ, build
from app.demo.setup import DemoRoles, prepare_demo_database
from app.main import create_app
from app.security import RateLimiter

DATABASE = "apiseed_demo"
ROLES = DemoRoles("test_seed_reader", "canaryseedreader1", "test_seed_writer", "canaryseedwriter1")
# The screenshots' frozen moment: Saturday 2026-10-17, 14:00 in Manila.
FROZEN = datetime(2026, 10, 17, 14, 0, tzinfo=TZ)


def url_for(username: str, password: str):
    server = make_url(os.environ["WAREHOUSE_URL"])
    return server.set(database=DATABASE, username=username, password=password)


READER_URL = url_for(ROLES.reader, ROLES.reader_password)
demo_app = create_app(
    Settings(
        app_env="demo",
        auth_mode="demo",
        public_base_url="http://testserver",
        warehouse_url=SecretStr(READER_URL.render_as_string(hide_password=False)),
        demo_session_secret=SecretStr("canary-demo-session-secret-0123456789abcdef"),
    ),
    environ={},
)


@pytest.fixture(scope="module")
def engines():
    server = make_url(os.environ["WAREHOUSE_URL"])
    admin = create_engine(
        server.set(database="postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True
    )
    prepare_demo_database(admin, DATABASE, ROLES, lock=[])
    writer = create_engine(url_for(ROLES.writer, ROLES.writer_password), hide_parameters=True)
    reader = create_engine(READER_URL)
    yield writer, reader

    writer.dispose()
    reader.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {DATABASE} WITH (FORCE)"))
        conn.execute(text(f"DROP ROLE IF EXISTS {ROLES.reader}"))
        conn.execute(text(f"DROP ROLE IF EXISTS {ROLES.writer}"))
    admin.dispose()


def seeded(engines, now: datetime, monkeypatch, name: str = "midweek") -> TestClient:
    """Replay scenario `name` as of `now`; return a demo visitor reading it."""
    writer, reader = engines
    replay(writer, build(name, now))
    monkeypatch.setenv("APP_ENV", "demo")
    monkeypatch.setenv("NOW_OVERRIDE", now.isoformat())
    demo_app.dependency_overrides[get_engine] = lambda: reader
    demo_app.state.rate_limiter = RateLimiter()  # every test starts a fresh visit
    client = TestClient(demo_app)
    assert client.post("/auth/demo").status_code == 204
    return client


@pytest.fixture(scope="module")
def frozen(engines) -> TestClient:
    """Built once for the module (a replay takes a few seconds). The tests that rebuild
    the database with another date or scenario come last in this file, for that reason."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        yield seeded(engines, FROZEN, monkeypatch)
    demo_app.dependency_overrides.clear()


def key_numbers(client: TestClient) -> dict:
    """What the tour talks about, as the pages show it."""
    dashboard = client.get("/api/v1/dashboard").json()
    health = client.get("/api/v1/pipeline/health").json()
    return {
        "streak": dashboard["streak"]["count"],
        "eaten_today": dashboard["calories"]["eaten"],
        "budget": dashboard["calories"]["budget"],
        "sources": {s["source"]: (s["status"], s["failures_7d"]) for s in health["sources"]},
        "quarantine": health["quarantine"]["by_reason"],
        "dq": (health["dq"]["passed"], health["dq"]["warnings"], health["dq"]["failed"]),
        "warnings": sorted(
            c["check_name"] for c in health["dq"]["checks"] if c["status"] == "warn"
        ),
    }


def table_counts(engine: Engine) -> dict:
    tables = [
        "raw.strava_activities", "raw.health_batches", "raw.health_samples",
        "core.fact_activity", "core.fact_set", "core.fact_dietary_sample",
        "core.fact_body_mass", "core.dim_exercise", "ops.pipeline_runs",
        "ops.dq_results", "ops.quarantine",
    ]  # fmt: skip
    with engine.connect() as conn:
        return {t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in tables}


# --- the numbers the tour quotes ------------------------------------------------------------


def test_the_key_numbers(frozen):
    assert key_numbers(frozen) == {
        "streak": 12,
        "eaten_today": 708,  # breakfast and lunch of 1,180 planned, pushed at 13:05
        "budget": 1853,
        "sources": {"health": ("ok", 0), "strava": ("ok", 1)},  # the timed-out sync
        "quarantine": {"unparsed_line": 2, "empty_exercise": 1},
        "dq": (12, 3, 0),
        "warnings": ["hevy_parse_coverage", "quarantine_open", "unmapped_exercises"],
    }


def test_todays_session_has_the_sets_the_screenshots_open(frozen):
    days = frozen.get("/api/v1/activities", params={"date": "2026-10-17"}).json()["days"]
    today = next(day for day in days if day["date"] == "2026-10-17")["activities"]
    full_body = next(a for a in today if a["title"] == "Full Body")
    bench = frozen.get(f"/api/v1/activities/{full_body['id']}").json()["exercises"][0]

    assert len(today) == 3
    assert bench["name"] == "Incline Bench Press"
    assert (bench["sets"][0]["weight_kg"], bench["sets"][0]["reps"]) == (20.0, 8)


# --- deterministic and idempotent ---------------------------------------------------------


def test_reseeding_gives_the_same_warehouse(engines, frozen, monkeypatch):
    first = (key_numbers(frozen), table_counts(engines[0]))
    again = seeded(engines, FROZEN, monkeypatch)

    assert (key_numbers(again), table_counts(engines[0])) == first


def test_building_a_scenario_is_pure():
    one, two = build("midweek", FROZEN), build("midweek", FROZEN)

    assert one.activities() == two.activities()
    assert one.events == two.events


# --- the realistic mess, all produced by the real code -------------------------------------


def runs(engine: Engine, where: str) -> list:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT * FROM ops.pipeline_runs WHERE {where}")).all()


def test_the_first_sync_backfills_in_two_runs(engines, frozen):
    statuses = [r.status for r in runs(engines[0], "source = 'strava' ORDER BY run_id")]

    assert statuses[:2] == ["partial", "success"]  # the 50-detail cap, then the rest


def test_a_timed_out_sync_is_failed_and_its_retry_succeeds(engines, frozen):
    failed = runs(engines[0], "source = 'strava' AND status = 'failed'")
    retry = runs(engines[0], f"source = 'strava' AND run_id = {failed[0].run_id + 1}")

    assert len(failed) == 1
    assert failed[0].error_message.startswith("TimeoutError: Strava did not answer")
    assert retry[0].status == "success"
    assert retry[0].started_at - failed[0].started_at == timedelta(minutes=30)


def test_a_resent_shortcut_push_is_absorbed(engines, frozen):
    resend = runs(engines[0], "source = 'health' AND rows_written = 0 AND rows_read > 0")

    assert len(resend) == 1


def test_an_old_freshness_warning_is_on_record_and_resolved(engines, frozen):
    with engines[0].connect() as conn:
        history = conn.execute(
            text(
                "SELECT status FROM ops.dq_results WHERE check_name = 'health_freshness' "
                "ORDER BY checked_at"
            )
        ).scalars().all()  # fmt: skip

    assert history[0] == "warn"  # the quiet Shortcut, five weeks ago
    assert history[-1] == "pass"


def test_one_day_over_budget_and_one_recovery_day_in_the_streak(engines, frozen):
    with engines[1].connect() as conn:
        statuses = conn.execute(
            text("SELECT calorie_status FROM mart.fn_daily_nutrition(:start, :end)"),
            {"start": FROZEN.date() - timedelta(days=11), "end": FROZEN.date()},
        ).scalars().all()  # fmt: skip
    week = frozen.get("/api/v1/dashboard").json()["streak"]["week"]

    assert statuses.count("over") == 1  # allowed once; two in a row would end the streak
    assert [day["kind"] for day in week].count("recovery") == 1


def test_the_raw_payloads_went_through_the_pipeline(engines, frozen):
    counts = table_counts(engines[0])
    with engines[0].connect() as conn:
        located = conn.execute(
            text("SELECT count(*) FROM raw.strava_activities WHERE payload ? 'map'")
        ).scalar_one()

    assert counts["core.fact_activity"] == counts["raw.strava_activities"] > 80
    assert counts["core.fact_set"] > 200
    assert located == 0


def test_the_seed_refuses_a_moment_in_the_future(engines):
    with pytest.raises(ValueError, match="future"):
        replay(engines[0], build("midweek", datetime.now(TZ) + timedelta(hours=2)))


def test_the_seed_refuses_a_database_not_named_demo(migrated_engine):
    with pytest.raises(ValueError, match="_demo"):
        replay(migrated_engine, build("midweek", FROZEN))


# --- last: these rebuild the demo database with another date or scenario ---------------


@pytest.mark.parametrize(
    ("now", "streak"),
    [
        # Any evening, whatever the weekday: today's workout and food are in. (Past dates
        # only: the pipeline's own clock can't be replayed into the future.)
        (datetime(2026, 10, 29, 20, 0, tzinfo=TZ), 12),
        (datetime(2026, 9, 20, 21, 30, tzinfo=TZ), 12),
        # Early morning: nothing synced today yet, so today isn't counted yet (and never
        # ends the streak before midnight). The tour must read the count, not quote it.
        (datetime(2026, 10, 29, 6, 0, tzinfo=TZ), 11),
    ],
)
def test_the_streak_does_not_depend_on_the_date(engines, monkeypatch, now, streak):
    client = seeded(engines, now, monkeypatch)
    numbers = key_numbers(client)
    demo_app.dependency_overrides.clear()

    assert numbers["streak"] == streak
    assert numbers["dq"][2] == 0  # no failed check on any date


@pytest.mark.parametrize("name", ["at_risk", "edge_empty"])
def test_the_other_screenshot_scenarios_build(engines, monkeypatch, name):
    client = seeded(engines, FROZEN, monkeypatch, name)
    status = client.get("/api/v1/dashboard").status_code
    demo_app.dependency_overrides.clear()

    assert status == 200
