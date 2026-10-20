"""Writes one checked batch to the database, all in one transaction (ARCHITECTURE.md 6.2).

Order inside the transaction: raw batch -> raw samples -> quarantine -> apply to core
-> run row. If any step fails, nothing from this request is kept.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Connection, Engine

from app.db import load_sql
from app.ingest.checks import Accepted, Rejected
from app.ingest.models import HealthBatchIn


@dataclass
class IngestResult:
    batch_id: UUID
    received: int
    accepted: int
    rejected: int
    duplicate: bool


def apply_batch(conn: Connection, batch_id: UUID) -> None:
    """Replace this batch's (day, type) pairs in core.fact_dietary_sample."""
    conn.execute(load_sql("health/apply_batch.sql"), {"batch_id": batch_id})


def record_run(
    conn: Connection, started_at: datetime, received: int, written: int, quarantined: int
) -> None:
    conn.execute(
        load_sql("ops/record_ingest_run.sql"),
        {
            "source": "health",
            "started_at": started_at,
            "rows_read": received,
            "rows_written": written,
            "rows_quarantined": quarantined,
        },
    )


def store_batch(
    engine: Engine,
    body: bytes,
    batch: HealthBatchIn,
    accepted: list[Accepted],
    rejected: list[Rejected],
    started_at: datetime,
) -> IngestResult:
    payload_sha256 = hashlib.sha256(body).hexdigest()
    received = len(accepted) + len(rejected)
    window = {"window_start": batch.window.start, "window_end": batch.window.end}

    with engine.begin() as conn:
        latest = conn.execute(load_sql("health/latest_batch.sql"), window).one_or_none()
        if latest is not None and latest.payload_sha256 == payload_sha256:
            # Identical re-send: store nothing, but log the run so freshness checks
            # can see the Shortcut is still sending.
            record_run(conn, started_at, received, written=0, quarantined=0)
            return IngestResult(latest.batch_id, received, 0, 0, duplicate=True)

        batch_id = conn.execute(
            load_sql("health/insert_batch.sql"),
            {
                **window,
                "device_tz": batch.device_tz,
                "payload_sha256": payload_sha256,
                "payload": body.decode(),
            },
        ).scalar_one()

        if accepted:
            conn.execute(
                load_sql("health/insert_sample.sql"),
                [
                    {
                        "batch_id": batch_id,
                        "idx": sample.idx,
                        "type": sample.type,
                        "value": sample.value,
                        "unit": sample.unit,
                        "start_ts": sample.start,
                        "local_date": sample.local_date,
                        "source": sample.source,
                    }
                    for sample in accepted
                ],
            )

        if rejected:
            conn.execute(
                load_sql("ops/insert_quarantine.sql"),
                [
                    {
                        "source": "health",
                        "entity_id": str(batch_id),
                        "line_no": sample.idx,
                        "raw_content": json.dumps(sample.raw),
                        "reason_code": sample.reason_code,
                        "error": sample.error,
                    }
                    for sample in rejected
                ],
            )

        apply_batch(conn, batch_id)
        record_run(conn, started_at, received, written=len(accepted), quarantined=len(rejected))

    return IngestResult(batch_id, received, len(accepted), len(rejected), duplicate=False)
