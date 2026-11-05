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
from app.demo import overrides
from app.demo.replay import ReseedBusy, replay
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
        "streak": 10,
        "eaten_today": 1068,  # breakfast and lunch of 1,780 planned, pushed at 13:05
        "budget": 1850,
        "sources": {"health": ("ok", 0), "strava": ("ok", 0)},  # no failures (Rob)
        "quarantine": {"unparsed_line": 2, "empty_exercise": 1},
        "dq": (13, 2, 0),
        "warnings": ["hevy_parse_coverage", "quarantine_open"],
    }


def test_the_tour_quotes_what_the_pages_show(frozen):
    story = frozen.get("/auth/me").json()["story"]
    dashboard = frozen.get("/api/v1/dashboard").json()
    checks = frozen.get("/api/v1/pipeline/health").json()["dq"]["checks"]

    assert story == {
        "streak_days": 10,
        "best_streak": 16,
        "n_checks": 15,
        "n_warnings": 2,
        "n_quarantined": 3,
        "lift_day": "2026-10-15",
        "eaten": 1068,
        "budget": 1850,
    }
    assert story["streak_days"] == dashboard["streak"]["count"]
    assert story["eaten"] == dashboard["calories"]["eaten"]
    assert story["budget"] == dashboard["calories"]["budget"]
    assert story["n_checks"] == len(checks)


def test_the_latest_lifting_session_has_parsed_sets(frozen):
    days = frozen.get("/api/v1/activities", params={"date": "2026-10-15"}).json()["days"]
    lifts = [
        a for day in days if day["date"] == "2026-10-15" for a in day["activities"]
        if a["type"] == "strength"
    ]  # fmt: skip
    detail = frozen.get(f"/api/v1/activities/{lifts[0]['id']}").json()

    assert len(lifts) == 1
    assert len(detail["exercises"]) >= 4
    assert all(len(exercise["sets"]) == 3 for exercise in detail["exercises"])


def test_lifting_sessions_and_personal_records(engines, frozen):
    with engines[0].connect() as conn:
        big_sessions = conn.execute(
            text(
                "SELECT count(*) FROM (SELECT activity_key FROM core.fact_set GROUP BY "
                "activity_key HAVING count(DISTINCT exercise_key) >= 4) AS sessions"
            )
        ).scalar_one()
    records = frozen.get("/api/v1/records").json()["records"]

    assert big_sessions >= 2
    assert len(records) >= 4


def test_today_is_partly_logged(frozen):
    dashboard = frozen.get("/api/v1/dashboard").json()

    assert 0 < dashboard["calories"]["eaten"] < dashboard["calories"]["budget"]
    assert dashboard["streak"]["message"] == "Nice. Today's counted."


def test_the_current_streak_has_one_over_budget_one_recovery_and_one_double_day(engines, frozen):
    start, end = FROZEN.date() - timedelta(days=9), FROZEN.date()
    with engines[1].connect() as conn:
        statuses = conn.execute(
            text("SELECT calorie_status FROM mart.fn_daily_nutrition(:start, :end)"),
            {"start": start, "end": end},
        ).scalars().all()  # fmt: skip
        recovery = conn.execute(text("SELECT count(*) FROM app.recovery_day")).scalar_one()
        doubles = conn.execute(
            text(
                "SELECT count(*) FROM (SELECT date_key FROM core.fact_activity "
                "GROUP BY date_key HAVING count(*) = 2) AS days"
            )
        ).scalar_one()

    assert statuses.count("over") == 1  # allowed once; two in a row would end the streak
    assert recovery == 1
    assert doubles == 1


# --- the realistic mess, all produced by the real code; no failures (Rob) --------------------


def runs(engine: Engine, where: str) -> list:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT * FROM ops.pipeline_runs WHERE {where}")).all()


def test_no_run_failed(engines, frozen):
    assert runs(engines[0], "status <> 'success'") == []


def test_a_resent_shortcut_push_is_absorbed(engines, frozen):
    resend = runs(engines[0], "source = 'health' AND rows_written = 0 AND rows_read > 0")

    assert len(resend) == 1


def test_quarantined_lines_have_plain_reasons(frozen):
    recent = frozen.get("/api/v1/pipeline/health").json()["quarantine"]["recent"]

    assert sorted(item["raw_snippet"] for item in recent) == [
        "Rowing (Machine)",
        "Set 1: 1.5km - 8min",
        "Set 2: 10 kg x 12 @ RPE 8",
    ]


def test_the_raw_payloads_went_through_the_pipeline(engines, frozen):
    counts = table_counts(engines[0])
    with engines[0].connect() as conn:
        located = conn.execute(
            text("SELECT count(*) FROM raw.strava_activities WHERE payload ? 'map'")
        ).scalar_one()

    assert counts["core.fact_activity"] == counts["raw.strava_activities"] > 20
    assert counts["core.fact_set"] > 100
    assert located == 0


def test_the_panel_shows_when_the_demo_was_rebuilt(frozen):
    rebuild = frozen.get("/api/v1/pipeline/health").json()["demo_rebuild"]

    assert 0 < rebuild["duration_ms"] < 60_000


def test_reseeding_never_touches_the_real_database(engines, migrated_engine, monkeypatch):
    def fingerprint() -> dict:
        with migrated_engine.connect() as conn:
            tables = conn.execute(
                text(
                    "SELECT table_schema || '.' || table_name FROM information_schema.tables "
                    "WHERE table_schema IN ('raw', 'core', 'ops', 'app') "
                    "AND table_type = 'BASE TABLE'"
                )
            ).scalars().all()  # fmt: skip
            return {
                t: conn.execute(text(f"SELECT md5(string_agg(x::text, '')) FROM {t} x")).scalar()
                for t in tables
            }

    before = fingerprint()
    seeded(engines, FROZEN, monkeypatch)

    assert fingerprint() == before


def test_two_reseeds_at_once_run_one_at_a_time(engines):
    """The advisory lock: while one rebuild's transaction holds it, another steps aside."""
    writer = engines[0]
    with writer.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('fitness-tracker demo reseed'))"))
        with pytest.raises(ReseedBusy):
            replay(create_engine(writer.url, hide_parameters=True), build("midweek", FROZEN))


def test_the_seed_refuses_a_moment_in_the_future(engines):
    with pytest.raises(ValueError, match="future"):
        replay(engines[0], build("midweek", datetime.now(TZ) + timedelta(hours=2)))


def test_the_seed_refuses_a_database_not_named_demo(migrated_engine):
    with pytest.raises(ValueError, match="_demo"):
        replay(migrated_engine, build("midweek", FROZEN))


# --- a visitor's own settings: applied at read time, never saved (D122) -------------------

BUDGET_1700 = {"X-Demo-Settings": '{"calorie_budget": 1700}'}


def week_markers(client: TestClient, headers=None) -> list[str]:
    week = client.get("/api/v1/dashboard", headers=headers).json()["streak"]["week"]
    return [day["calorie_status"] for day in week]


def test_a_lower_budget_changes_the_streak_and_the_week_markers(frozen):
    dashboard = frozen.get("/api/v1/dashboard", headers=BUDGET_1700).json()

    assert dashboard["streak"]["count"] < 10
    assert dashboard["calories"]["budget"] == 1700
    assert week_markers(frozen, BUDGET_1700).count("over") > week_markers(frozen).count("over")


def test_relaxed_weekends_apply_for_the_visitor_only(frozen):
    relaxed = {"X-Demo-Settings": '{"lenient_weekends": true}'}

    assert frozen.get("/api/v1/me", headers=relaxed).json()["lenient_weekends"] is True
    assert frozen.get("/api/v1/me").json()["lenient_weekends"] is False


def test_the_me_page_shows_the_visitors_settings_clamped(frozen):
    wild = {"X-Demo-Settings": '{"calorie_budget": 99999, "protein_goal": -5, "nickname": "Ana"}'}
    me = frozen.get("/api/v1/me", headers=wild).json()

    assert me["targets"]["calorie_budget"] == 6000
    assert me["targets"]["protein_goal"] == 0
    assert me["nickname"] == "Ana"


def test_settings_are_never_written(engines, frozen):
    before = table_counts(engines[0])
    with engines[0].connect() as conn:
        targets = conn.execute(text("SELECT * FROM app.target_history")).all()

    frozen.get("/api/v1/me", headers=BUDGET_1700)
    saved = frozen.put("/api/v1/me", json={"targets": {"calorie_budget": 1700, "protein_goal": 1}})

    assert saved.status_code == 403  # the real write route stays shut
    assert table_counts(engines[0]) == before
    with engines[0].connect() as conn:
        assert conn.execute(text("SELECT * FROM app.target_history")).all() == targets


def test_settings_never_reach_the_next_request_on_the_same_connection(engines, frozen):
    one_connection = create_engine(READER_URL, pool_size=1, max_overflow=0)
    demo_app.dependency_overrides[get_engine] = lambda: one_connection
    try:
        mine = frozen.get("/api/v1/dashboard", headers=BUDGET_1700).json()["streak"]["count"]
        next_visitor = TestClient(demo_app)
        next_visitor.post("/auth/demo")
        theirs = next_visitor.get("/api/v1/dashboard").json()["streak"]["count"]
    finally:
        demo_app.dependency_overrides[get_engine] = lambda: engines[1]
        one_connection.dispose()

    assert mine < theirs == 10


def test_settings_end_with_their_transaction_even_after_a_commit(engines, frozen):
    """The guarantee itself: a value lasts one transaction, committed or not, so a pooled
    connection (Neon's PgBouncer hands it to the next client) never carries it on."""
    one_connection = create_engine(READER_URL, pool_size=1, max_overflow=0)
    token = overrides.current.set(overrides.DemoSettings(calorie_budget=1700))
    try:
        with one_connection.begin() as conn:  # commits, unlike a page's read
            inside = conn.execute(text("SELECT app.demo_setting('calorie_budget')")).scalar_one()
    finally:
        overrides.current.reset(token)
    with one_connection.connect() as conn:
        after = conn.execute(text("SELECT app.demo_setting('calorie_budget')")).scalar_one()
    one_connection.dispose()

    assert (inside, after) == ("1700", None)


@pytest.mark.parametrize(
    ("value", "status"),
    [
        ("not json", 422),
        ('{"calorie_budget": "lots"}', 422),
        ('{"nickname": "' + "x" * 600 + '"}', 413),
    ],
)
def test_bad_settings_are_refused(frozen, value, status):
    assert frozen.get("/api/v1/dashboard", headers={"X-Demo-Settings": value}).status_code == status


def test_the_real_app_ignores_demo_settings(client):
    plain = client.get("/api/v1/me").json()

    assert client.get("/api/v1/me", headers=BUDGET_1700).json() == plain


# --- last: these rebuild the demo database with another date or scenario ---------------


@pytest.mark.parametrize(
    ("now", "streak"),
    [
        # A Wednesday and a Saturday (past dates only: the pipeline's own clock can't be
        # replayed into the future), at four times of day. Before today's first entries
        # (03:00) today isn't counted yet, and never ends the streak before midnight.
        (datetime(2026, 10, 21, hour, 0, tzinfo=TZ), streak)
        for hour, streak in ((3, 9), (9, 10), (15, 10), (21, 10))
    ]
    + [
        (datetime(2026, 10, 24, hour, 0, tzinfo=TZ), streak)
        for hour, streak in ((3, 9), (9, 10), (15, 10), (21, 10))
    ],
)
def test_the_streak_does_not_depend_on_the_date(engines, monkeypatch, now, streak):
    client = seeded(engines, now, monkeypatch)
    numbers = key_numbers(client)
    story = client.get("/auth/me").json()["story"]
    records = client.get("/api/v1/records").json()["records"]
    demo_app.dependency_overrides.clear()

    assert numbers["streak"] == story["streak_days"] == streak
    assert numbers["budget"] == 1850 == story["budget"]
    # Before today's first entry the tour has no "eaten" to quote, and drops the sentence.
    assert story["eaten"] == (numbers["eaten_today"] or None)
    assert numbers["dq"][2] == 0  # no failed check at any time
    assert numbers["sources"] == {"health": ("ok", 0), "strava": ("ok", 0)}
    assert len(records) >= 2


@pytest.mark.parametrize("name", ["at_risk", "edge_empty"])
def test_the_other_screenshot_scenarios_build(engines, monkeypatch, name):
    client = seeded(engines, FROZEN, monkeypatch, name)
    status = client.get("/api/v1/dashboard").status_code
    demo_app.dependency_overrides.clear()

    assert status == 200
