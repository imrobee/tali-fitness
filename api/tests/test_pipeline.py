"""GET /api/v1/pipeline/health (clock frozen at Tue 2026-10-20 20:00 Manila = 12:00 UTC)."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import TEST_API_KEY
from sqlalchemy import Engine, text

HEADERS = {"X-API-Key": TEST_API_KEY}
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def add_run(engine: Engine, source: str, hours_ago: float, status: str = "success") -> None:
    at = NOW - timedelta(hours=hours_ago)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ops.pipeline_runs (source, started_at, finished_at, status) "
                "VALUES (:source, :at, :at, :status)"
            ),
            {"source": source, "at": at, "status": status},
        )


def source_status(client, name: str) -> dict:
    body = client.get("/api/v1/pipeline/health", headers=HEADERS).json()
    return next(s for s in body["sources"] if s["source"] == name)


def add_quarantine(engine: Engine, reason: str, raw: str = "Set 1: ???", resolved=False) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ops.quarantine (source, entity_id, line_no, raw_content, "
                "reason_code, resolved_at) VALUES ('strava', '1', 3, :raw, :reason, "
                "CASE WHEN :resolved THEN now() END)"
            ),
            {"raw": raw, "reason": reason, "resolved": resolved},
        )


def add_dq_run(engine: Engine, results: list[tuple[str, str]], hours_ago: float = 0.5) -> int:
    at = NOW - timedelta(hours=hours_ago)
    with engine.begin() as conn:
        run_id = conn.execute(
            text(
                "INSERT INTO ops.pipeline_runs (source, started_at, finished_at, status) "
                "VALUES ('dq', :at, :at, 'success') RETURNING run_id"
            ),
            {"at": at},
        ).scalar_one()
        for name, status in results:
            conn.execute(
                text(
                    "INSERT INTO ops.dq_results (run_id, check_name, status, observed_value, "
                    "threshold, checked_at) VALUES (:run, :name, :status, 1, 'limit', :at)"
                ),
                {"run": run_id, "name": name, "status": status, "at": at},
            )
    return run_id


# --- sources -------------------------------------------------------------------------------


def test_the_response_carries_the_servers_clock(client):
    body = client.get("/api/v1/pipeline/health", headers=HEADERS).json()

    assert body["now"] == "2026-10-20T20:00:00+08:00"


def test_a_source_that_never_synced_is_failed(client):
    body = client.get("/api/v1/pipeline/health", headers=HEADERS).json()

    assert [(s["source"], s["status"], s["last_success_at"]) for s in body["sources"]] == [
        ("health", "failed", None),
        ("strava", "failed", None),
    ]


@pytest.mark.parametrize(
    ("source", "hours_ago", "expected"),
    [
        ("strava", 1, "ok"),
        ("strava", 7, "delayed"),
        ("strava", 25, "failed"),
        ("health", 10, "ok"),  # health warns after 48 h, not 6
        ("health", 50, "delayed"),
        ("health", 97, "failed"),
    ],
)
def test_source_status_follows_its_thresholds(client, engine, source, hours_ago, expected):
    add_run(engine, source, hours_ago)

    assert source_status(client, source)["status"] == expected


def test_a_failed_last_run_makes_the_source_failed(client, engine):
    add_run(engine, "strava", 1)
    add_run(engine, "strava", 0.5, status="failed")

    assert source_status(client, "strava")["status"] == "failed"


def test_failures_are_counted_for_seven_days_only(client, engine):
    add_run(engine, "strava", 1)
    add_run(engine, "strava", 24 * 3, status="failed")
    add_run(engine, "strava", 24 * 10, status="failed")

    assert source_status(client, "strava")["failures_7d"] == 1


def test_a_partial_strava_run_counts_as_success_but_not_for_health(client, engine):
    add_run(engine, "strava", 1, status="partial")
    add_run(engine, "health", 1, status="partial")

    assert source_status(client, "strava")["status"] == "ok"
    assert source_status(client, "health")["status"] == "failed"


# --- quarantine ----------------------------------------------------------------------------


def test_quarantine_counts_open_rows_by_reason(client, engine):
    add_quarantine(engine, "unparsed_line")
    add_quarantine(engine, "unparsed_line")
    add_quarantine(engine, "bad_unit")
    add_quarantine(engine, "bad_unit", resolved=True)

    quarantine = client.get("/api/v1/pipeline/health", headers=HEADERS).json()["quarantine"]

    assert quarantine["open"] == 3
    assert quarantine["by_reason"] == {"unparsed_line": 2, "bad_unit": 1}


def test_quarantine_shows_the_20_most_recent_with_short_snippets(client, engine):
    for index in range(25):
        add_quarantine(engine, "unparsed_line", raw="x" * 500 + str(index))

    recent = client.get("/api/v1/pipeline/health", headers=HEADERS).json()["quarantine"]["recent"]

    assert len(recent) == 20
    assert all(len(item["raw_snippet"]) == 200 for item in recent)
    assert recent[0]["reason_code"] == "unparsed_line"


# --- data quality --------------------------------------------------------------------------


def test_dq_shows_the_latest_run_only(client, engine):
    add_dq_run(engine, [("strava_freshness", "pass")], hours_ago=5)
    add_dq_run(
        engine,
        [("strava_freshness", "warn"), ("set_range", "fail"), ("target_present", "pass")],
    )

    dq = client.get("/api/v1/pipeline/health", headers=HEADERS).json()["dq"]

    assert (dq["passed"], dq["warnings"], dq["failed"]) == (1, 1, 1)
    assert [check["check_name"] for check in dq["checks"]] == [
        "strava_freshness",
        "set_range",
        "target_present",
    ]


def test_dq_is_empty_before_any_run(client):
    dq = client.get("/api/v1/pipeline/health", headers=HEADERS).json()["dq"]

    assert dq == {"passed": 0, "warnings": 0, "failed": 0, "checked_at": None, "checks": []}


def test_pipeline_health_needs_the_api_key(client):
    assert client.get("/api/v1/pipeline/health").status_code == 401
