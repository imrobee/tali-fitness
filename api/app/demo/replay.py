"""Build a demo scenario by running its raw payloads through the real pipeline (D119, D121).

Nothing here inserts warehouse rows itself. Each event in the scenario's timeline calls
the same code production runs:
- a Shortcut push: app.ingest.service.ingest_body (the POST /ingest/health route's body);
- a Strava sync: the strava_sync DAG's steps from pipeline/include (sync, core load, Hevy
  parse, quarantine), with SyntheticStrava in place of Strava's API and no token;
- a data-quality run: the data_quality DAG's 15 checks.
The only direct writes are the manual entries a person makes in the app (targets, the
weight goal, recovery days), and moving each replayed step's bookkeeping times to the
moment it stands for (the database stamps them with its own clock).

The whole rebuild is ONE transaction (OneTransaction below): visitors keep reading the
old demo, never a half-built one, until it commits. A transaction-level advisory lock
makes sure only one rebuild runs at a time.

Runs as demo_seed, which owns the demo database and can open no other.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

from sqlalchemy import Connection, Engine

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


class ReseedBusy(Exception):
    """Another rebuild holds the lock; this one stepped aside."""


class OneTransaction:
    """Stands in for an Engine, so the pipeline code runs inside one outer transaction.

    The pipeline only ever calls engine.begin() and engine.connect(). Here both hand out
    the same connection: begin() opens a SAVEPOINT, so a step that fails (the planned
    Strava time-out) rolls back alone, exactly as its own transaction would."""

    def __init__(self, conn: Connection) -> None:
        self.conn = conn
        self.url = conn.engine.url

    @contextmanager
    def begin(self) -> Iterator[Connection]:
        with self.conn.begin_nested():
            yield self.conn

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        yield self.conn


def replay(engine: Engine, scenario: Scenario) -> float:
    """Empty the demo database and build `scenario` in it, in one transaction. Returns
    the seconds it took. Running it twice gives the same result: the reset makes it
    idempotent, the fixed seed makes it deterministic."""
    require_demo_name(engine.url.database)
    started = time.monotonic()
    with engine.begin() as conn:
        if not conn.execute(load_sql("demo/reseed_lock.sql")).scalar_one():
            raise ReseedBusy("Another demo rebuild is running; this one stopped.")
        if scenario.now > conn.execute(load_sql("demo/now.sql")).scalar_one():
            # Some bookkeeping is stamped with the database's own now(), and a run can't
            # end before it started: the demo can be built as of now or a past moment only.
            raise ValueError("Can't build the demo as of a moment in the future.")
        conn.execute(load_sql("demo/reset.sql"))
        db = OneTransaction(conn)
        enter_manual_entries(conn, scenario)
        strava = SyntheticStrava(scenario.activities())
        for event in scenario.events:
            if event.kind == "health":
                push_health(db, scenario, event)
            elif event.kind == "strava":
                sync_strava(db, strava, event)
            else:
                check_quality(db, event)
            retime(conn, event)
        seconds = time.monotonic() - started
        conn.execute(
            load_sql("demo/seed_state_save.sql"),
            {
                "scenario": scenario.name,
                "as_of": scenario.now,
                "duration_ms": round(seconds * 1000),
            },
        )
    return time.monotonic() - started


def enter_manual_entries(conn: Connection, scenario: Scenario) -> None:
    """What a person types into the app: Me page targets, recovery days."""
    set_up = scenario.today - timedelta(days=200)  # before the oldest data
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


def push_health(db: OneTransaction, scenario: Scenario, event: Event) -> None:
    body = health_body(scenario, event.day, event.at)
    if body is None:
        return  # nothing to send: the Shortcut would not push
    today = event.at.astimezone(TZ).date()
    for _ in range(2 if event.resend else 1):  # a resend is the identical payload again
        ingest_body(db, body, started_at=event.at, today=today)


def sync_strava(db: OneTransaction, strava: SyntheticStrava, event: Event) -> None:
    """The strava_sync DAG's tasks in order (pipeline/dags/strava_sync.py), minus the token
    refresh: the demo has no token. A failed step is recorded on the run, as in Airflow,
    and the later steps do not run."""
    strava.now = event.at
    strava.fail_next_detail = event.fail
    with db.begin() as conn:
        run_id = runs.start_run(conn, source=STRAVA, airflow_run_id=None)
    try:
        with runs.record_failure(db, run_id):
            result = sync_with_token(db, strava, None, now=event.at, backfill_days=BACKFILL_DAYS)
            status = "partial" if result.hit_cap else "success"
            with db.begin() as conn:
                runs.finish_run(conn, run_id, status, result.listed, result.written)
        with runs.record_failure(db, run_id):
            transform_activities(db)
        with runs.record_failure(db, run_id):
            parsed = parse_pending(db)
            with db.begin() as conn:
                conn.execute(
                    pipeline_sql("ops/add_quarantined.sql"),
                    {"run_id": run_id, "count": parsed.quarantined},
                )
    except TimeoutError:
        pass  # the planned time-out: the run is already marked failed; the retry follows
    finally:
        with db.begin() as conn:
            runs.close_run(conn, run_id)


def check_quality(db: OneTransaction, event: Event) -> None:
    """The data_quality DAG (pipeline/dags/data_quality.py), at the event's moment."""
    with db.begin() as conn:
        run_id = runs.start_run(conn, source="dq", airflow_run_id=None)
    results = run_checks(db, now=event.at, run_id=run_id)
    with db.begin() as conn:
        runs.finish_run(conn, run_id, "success", len(CHECKS), len(results))
        runs.close_run(conn, run_id)


def retime(conn: Connection, event: Event) -> None:
    """Inside one transaction now() never moves, so the rows this step stamped with now()
    are exactly the ones still showing it; they move to the step's own moment."""
    for name in RETIME:
        conn.execute(load_sql(f"demo/retime_{name}.sql"), {"at": event.at})
