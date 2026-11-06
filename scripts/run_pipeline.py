"""Run the pipeline without Airflow: the production schedule (DECISIONS D132).

Usage (in the api container, which has the pipeline code at its Airflow paths; see
.github/workflows/pipeline.yml):
    python /scripts/run_pipeline.py strava    # the Strava sync, like the strava_sync DAG
    python /scripts/run_pipeline.py dq        # the data-quality checks, like data_quality
    python /scripts/run_pipeline.py all       # both, in that order (the hourly job)

The steps are include/jobs.py, the same functions the Airflow tasks call, and each run is
a row in ops.pipeline_runs, as with Airflow. Reads WAREHOUSE_URL, STRAVA_CLIENT_ID,
STRAVA_CLIENT_SECRET and BACKFILL_DAYS from the environment. Prints only run ids and
statuses: the job's log is public. Exits 1 if a job failed, so the workflow shows it.
"""

import os
import sys
from datetime import UTC, datetime

from include import jobs
from include.db import get_engine
from include.strava.client import StravaClient

JOBS = ("strava", "dq", "all")


def main(argv: list[str]) -> int:
    which = argv[1] if len(argv) > 1 else "all"
    if which not in JOBS:
        print(f"Usage: run_pipeline.py {'|'.join(JOBS)}", file=sys.stderr)
        return 2
    engine = get_engine()
    ok = True
    if which in ("strava", "all"):
        result = jobs.run_strava_sync(
            engine,
            StravaClient.from_env(),
            now=datetime.now(UTC),
            backfill_days=int(os.environ.get("BACKFILL_DAYS", "90")),
        )
        print(f"strava_sync run {result.run_id}: {'ok' if result.ok else 'failed'}")
        ok = ok and result.ok
    if which in ("dq", "all"):
        # After the sync, so the checks see its rows (Airflow ran them at :30 for this).
        result = jobs.run_data_quality(engine, now=datetime.now(UTC))
        print(f"data_quality run {result.run_id}: {'ok' if result.ok else 'failed'}")
        ok = ok and result.ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
