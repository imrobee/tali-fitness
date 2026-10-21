"""The five M1 data-quality checks: a pass test and a fail test for each (ARCHITECTURE.md 9)."""

from datetime import UTC, datetime, timedelta

import pytest
from day_builder import add_activity
from sqlalchemy import Engine, text

from include import runs
from include.db import load_sql
from include.dq.checks import CHECKS, run_check, run_checks
from include.strava import sync

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def finished_run(engine: Engine, source: str, hours_ago: float, status: str = "success") -> None:
    finished_at = NOW - timedelta(hours=hours_ago)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ops.pipeline_runs (source, started_at, finished_at, status) "
                "VALUES (:source, :at, :at, :status)"
            ),
            {"source": source, "at": finished_at, "status": status},
        )


def status_of(engine: Engine, check: str) -> str:
    return run_check(engine, check, NOW).status


# --- freshness -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("check", "source", "hours_ago", "expected"),
    [
        ("strava_freshness", "strava", 1, "pass"),
        ("strava_freshness", "strava", 7, "warn"),
        ("strava_freshness", "strava", 25, "fail"),
        ("health_freshness", "health", 10, "pass"),
        ("health_freshness", "health", 50, "warn"),
        ("health_freshness", "health", 97, "fail"),
    ],
)
def test_freshness_thresholds(engine, check, source, hours_ago, expected):
    finished_run(engine, source, hours_ago)

    result = run_check(engine, check, NOW)

    assert result.status == expected
    assert float(result.observed_value) == hours_ago


@pytest.mark.parametrize("check", ["strava_freshness", "health_freshness"])
def test_never_synced_fails(engine, check):
    assert status_of(engine, check) == "fail"


def test_failed_runs_do_not_count_as_fresh(engine):
    finished_run(engine, "strava", 30)
    finished_run(engine, "strava", 1, status="failed")

    assert status_of(engine, "strava_freshness") == "fail"


def test_a_partial_strava_run_counts_as_fresh(engine):
    finished_run(engine, "strava", 1, status="partial")

    assert status_of(engine, "strava_freshness") == "pass"


def test_a_dead_strava_token_shows_a_failed_run_and_a_freshness_warning(engine):
    # PROJECT_PLAN Slice 5 acceptance: the last good sync was 7 h ago, then the token
    # refresh starts failing (for example a revoked app).
    finished_run(engine, "strava", 7)
    with engine.begin() as conn:
        sync.save_tokens(
            conn,
            {"access_token": "a", "refresh_token": "r", "expires_at": int(NOW.timestamp())},
        )
        run_id = runs.start_run(conn, source="strava", airflow_run_id="scheduled__test")

    class RevokedStrava:
        def refresh(self, refresh_token: str) -> dict:
            raise RuntimeError("Strava HTTP 401 for https://www.strava.com/oauth/token")

    with pytest.raises(RuntimeError), runs.record_failure(engine, run_id):
        sync.ensure_fresh_token(engine, RevokedStrava(), now=NOW)

    with engine.connect() as conn:
        failed = conn.execute(
            text("SELECT status, error_message FROM ops.pipeline_runs WHERE run_id = :id"),
            {"id": run_id},
        ).one()
    assert failed.status == "failed"
    assert "401" in failed.error_message
    assert status_of(engine, "strava_freshness") == "warn"


# --- activity_unique and row_reconcile -----------------------------------------------------


def test_activity_unique_passes_with_distinct_activities(engine):
    add_activity(engine, NOW.date())
    add_activity(engine, NOW.date() - timedelta(days=1))

    assert status_of(engine, "activity_unique") == "pass"


def test_activity_unique_fails_on_a_duplicate(engine):
    # The UNIQUE constraint normally makes this impossible, so the test removes it inside
    # a transaction that is rolled back afterwards.
    add_activity(engine, NOW.date())
    with engine.connect() as conn:
        transaction = conn.begin()
        conn.execute(
            text("ALTER TABLE core.fact_activity DROP CONSTRAINT fact_activity_strava_id_key")
        )
        conn.execute(
            text(
                "INSERT INTO core.fact_activity (strava_id, date_key, activity_type_key, "
                "started_at, started_local, ended_at, duration_s, source_fetched_at) "
                "SELECT strava_id, date_key, activity_type_key, started_at, started_local, "
                "ended_at, duration_s, source_fetched_at FROM core.fact_activity"
            )
        )
        row = conn.execute(load_sql("dq/activity_unique.sql"), {"now": NOW}).one()
        transaction.rollback()

    assert (row.status, row.observed_value) == ("fail", 1)


def test_row_reconcile_passes_when_every_raw_activity_reached_core(engine):
    add_activity(engine, NOW.date())

    assert status_of(engine, "row_reconcile") == "pass"


def test_row_reconcile_fails_when_raw_has_more(engine):
    add_activity(engine, NOW.date())
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO raw.strava_activities (strava_id, payload, fetched_at) "
                "VALUES (999, '{}', now())"
            )
        )

    result = run_check(engine, "row_reconcile", NOW)

    assert (result.status, result.observed_value) == ("fail", 1)


# --- hevy_parse_coverage -------------------------------------------------------------------


def set_parse_statuses(engine: Engine, statuses: list[str], days_ago: int = 1) -> None:
    for index, status in enumerate(statuses):
        day = NOW.date() - timedelta(days=days_ago + index)
        add_activity(engine, day)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE core.fact_activity SET parse_status = :status, "
                    "started_at = CAST(:started AS timestamptz) WHERE strava_id = :id"
                ),
                {
                    "status": status,
                    "started": f"{day}T08:00:00+08:00",
                    "id": day.year * 10000 + day.month * 100 + day.day,
                },
            )


@pytest.mark.parametrize(
    ("statuses", "expected_status", "expected_percent"),
    [
        (["ok"] * 20, "pass", 100),
        (["ok"] * 19 + ["partial"], "pass", 95),
        (["ok"] * 9 + ["partial"], "warn", 90),
        (["ok", "partial"], "fail", 50),
    ],
)
def test_hevy_parse_coverage_thresholds(engine, statuses, expected_status, expected_percent):
    set_parse_statuses(engine, statuses)

    result = run_check(engine, "hevy_parse_coverage", NOW)

    assert (result.status, float(result.observed_value)) == (expected_status, expected_percent)


def test_hevy_parse_coverage_passes_with_no_hevy_activities(engine):
    set_parse_statuses(engine, ["not_hevy", "not_applicable"])

    result = run_check(engine, "hevy_parse_coverage", NOW)

    assert (result.status, result.observed_value) == ("pass", None)


def test_hevy_parse_coverage_ignores_activities_older_than_30_days(engine):
    set_parse_statuses(engine, ["partial"], days_ago=40)
    set_parse_statuses(engine, ["ok"], days_ago=1)

    assert run_check(engine, "hevy_parse_coverage", NOW).status == "pass"


# --- runner --------------------------------------------------------------------------------


def test_run_checks_stores_one_result_per_check(engine):
    finished_run(engine, "strava", 1)
    with engine.begin() as conn:
        run_id = runs.start_run(conn, source="dq", airflow_run_id="manual__test")

    results = run_checks(engine, NOW, run_id)

    with engine.connect() as conn:
        stored = conn.execute(
            text("SELECT check_name, status FROM ops.dq_results WHERE run_id = :id ORDER BY id"),
            {"id": run_id},
        ).all()
    assert [r.check_name for r in stored] == list(CHECKS)
    assert [(r.check_name, r.status) for r in results] == [(s.check_name, s.status) for s in stored]
