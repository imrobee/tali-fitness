"""Build a demo scenario by running its raw payloads through the real pipeline (D119).

Nothing here inserts warehouse rows itself. Each event in the scenario's timeline calls
the same code production runs:
- a Shortcut push: app.ingest.service.ingest_body (the POST /ingest/health route's body);
- a Strava sync: the strava_sync DAG's steps from pipeline/include (sync, core load, Hevy
  parse, quarantine), with SyntheticStrava in place of Strava's API and no token;
- a data-quality run: the data_quality DAG's 15 checks.
The only direct writes are the manual entries a person makes in the app (targets, the
weight goal, a recovery day), and moving each replayed step's bookkeeping times to the
moment it stands for (the database stamps them with its own clock).

Runs as the demo writer, which owns the demo database and can open no other.
"""

from datetime import datetime, timedelta

from sqlalchemy import Engine

from app.db import load_sql
from app.demo.scenario import TZ, Event, Scenario, SyntheticStrava, health_body
from app.demo.setup import require_demo_name
from app.ingest.service import ingest_body
from include import runs
from include.core.activities import transform_activities
from include.core.sets import parse_pending
from include.db import load_sql as pipeline_sql
from include.dq.checks import CHECKS, run_checks
from include.strava.sync import SOURCE as STRAVA
from include.strava.sync import sync_with_token

BACKFILL_DAYS = 170  # the first sync reaches back past the oldest synthetic activity
RETIME = ("runs", "dq", "quarantine", "batches", "watermarks")


def replay(engine: Engine, scenario: Scenario) -> None:
    """Empty the demo database, then build `scenario` in it. Running it twice gives the
    same result: the reset makes it idempotent, the fixed seed makes it deterministic."""
    require_demo_name(engine.url.database)
    with engine.connect() as conn:
        wall_clock = conn.execute(load_sql("demo/wall_clock.sql")).scalar_one()
    if scenario.now > wall_clock:
        # Some bookkeeping is stamped with the database's own now(), and a run can't end
        # before it started: the demo can be built as of now or any past moment only.
        raise ValueError("Can't build the demo as of a moment in the future.")
    with engine.begin() as conn:
        conn.execute(load_sql("demo/reset.sql"))
        conn.execute(load_sql("demo/reset_profile.sql"))
    enter_manual_entries(engine, scenario)
    strava = SyntheticStrava(scenario.activities())
    for event in scenario.events:
        with engine.connect() as conn:
            since = conn.execute(load_sql("demo/wall_clock.sql")).scalar_one()
        if event.kind == "health":
            push_health(engine, scenario, event)
        elif event.kind == "strava":
            sync_strava(engine, strava, event)
        else:
            check_quality(engine, event)
        retime(engine, since, event.at)


def enter_manual_entries(engine: Engine, scenario: Scenario) -> None:
    """What a person types into the app: Me page targets, a recovery day."""
    set_up = scenario.today - timedelta(days=200)  # before the oldest data
    with engine.begin() as conn:
        conn.execute(load_sql("demo/set_nickname.sql"), {"nickname": scenario.nickname})
        if scenario.target:
            conn.execute(
                load_sql("demo/insert_target.sql"), {"effective_from": set_up, **scenario.target}
            )
        if scenario.weight_goal_kg is not None:
            conn.execute(
                load_sql("demo/insert_weight_goal.sql"),
                {"effective_from": set_up, "goal_kg": scenario.weight_goal_kg},
            )
        for day in scenario.recovery:
            conn.execute(load_sql("demo/insert_recovery.sql"), {"day": day})


def push_health(engine: Engine, scenario: Scenario, event: Event) -> None:
    body = health_body(scenario, event.day, event.at)
    if body is None:
        return  # nothing to send: the Shortcut would not push
    today = event.at.astimezone(TZ).date()
    for _ in range(2 if event.resend else 1):  # a resend is the identical payload again
        ingest_body(engine, body, started_at=event.at, today=today)


def sync_strava(engine: Engine, strava: SyntheticStrava, event: Event) -> None:
    """The strava_sync DAG's tasks in order (pipeline/dags/strava_sync.py), minus the token
    refresh: the demo has no token. A failed step is recorded on the run, as in Airflow,
    and the later steps do not run."""
    strava.now = event.at
    strava.fail_next_detail = event.fail
    with engine.begin() as conn:
        run_id = runs.start_run(conn, source=STRAVA, airflow_run_id=None)
    try:
        with runs.record_failure(engine, run_id):
            result = sync_with_token(
                engine, strava, None, now=event.at, backfill_days=BACKFILL_DAYS
            )
            status = "partial" if result.hit_cap else "success"
            with engine.begin() as conn:
                runs.finish_run(conn, run_id, status, result.listed, result.written)
        with runs.record_failure(engine, run_id):
            transform_activities(engine)
        with runs.record_failure(engine, run_id):
            parsed = parse_pending(engine)
            with engine.begin() as conn:
                conn.execute(
                    pipeline_sql("ops/add_quarantined.sql"),
                    {"run_id": run_id, "count": parsed.quarantined},
                )
    except TimeoutError:
        pass  # the planned time-out: the run is already marked failed; the retry follows
    finally:
        with engine.begin() as conn:
            runs.close_run(conn, run_id)


def check_quality(engine: Engine, event: Event) -> None:
    """The data_quality DAG (pipeline/dags/data_quality.py), at the event's moment."""
    with engine.begin() as conn:
        run_id = runs.start_run(conn, source="dq", airflow_run_id=None)
    results = run_checks(engine, now=event.at, run_id=run_id)
    with engine.begin() as conn:
        runs.finish_run(conn, run_id, "success", len(CHECKS), len(results))
        runs.close_run(conn, run_id)


def retime(engine: Engine, since: datetime, at: datetime) -> None:
    with engine.begin() as conn:
        for name in RETIME:
            conn.execute(load_sql(f"demo/retime_{name}.sql"), {"since": since, "at": at})
