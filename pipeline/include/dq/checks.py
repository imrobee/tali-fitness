"""Data-quality checks (ARCHITECTURE.md section 9).

Each check is a plain SQL file in db/sql/dq/ that returns one row:
(observed_value, status, threshold). The thresholds live in the SQL, next to the rule.
A failing check is a finding, not a crash: the run still succeeds and the result is
stored in ops.dq_results for the pipeline health panel.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Engine

from include.db import load_sql

# All 15 checks, in the order of ARCHITECTURE.md section 9.
CHECKS = (
    "strava_freshness",
    "health_freshness",
    "activity_unique",
    "activity_not_null",
    "activity_duration_range",
    "set_range",
    "calorie_daily_range",
    "fk_integrity",
    "row_reconcile",
    "hevy_parse_coverage",
    "quarantine_open",
    "unmapped_exercises",
    "possible_duplicate_activity",
    "target_present",
    "days_with_activity_no_calories",
)


@dataclass
class CheckResult:
    check_name: str
    status: str  # pass | warn | fail
    observed_value: Decimal | None
    threshold: str


def run_check(engine: Engine, check_name: str, now: datetime) -> CheckResult:
    with engine.connect() as conn:
        row = conn.execute(load_sql(f"dq/{check_name}.sql"), {"now": now}).one()
    return CheckResult(check_name, row.status, row.observed_value, row.threshold)


def run_checks(engine: Engine, now: datetime, run_id: int | None) -> list[CheckResult]:
    """Run every check and store the results under one pipeline run."""
    results = [run_check(engine, name, now) for name in CHECKS]
    with engine.begin() as conn:
        conn.execute(
            load_sql("ops/insert_dq_result.sql"),
            [
                {
                    "run_id": run_id,
                    "check_name": result.check_name,
                    "status": result.status,
                    "observed_value": result.observed_value,
                    "threshold": result.threshold,
                }
                for result in results
            ],
        )
    return results
