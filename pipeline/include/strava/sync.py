"""Incremental Strava sync into raw.strava_activities (ARCHITECTURE.md section 6.1).

How one run works:
1. Read the watermark: the newest activity start time already loaded.
2. List activities that started after (watermark - 7 days). The 7-day lookback re-reads
   recent activities, so a description edited after upload is picked up.
3. Fetch the detail of each listed activity (the list has no description), at most
   `detail_cap` per run to respect Strava's rate limits. Activities not yet loaded go
   first (oldest first); already-loaded ones inside the lookback are refreshed with what
   is left of the cap. Otherwise a long backfill would re-fetch the same activities
   every run and never finish.
4. Write each activity and advance the watermark in one transaction. If the run dies
   midway, everything written so far stays and the next run continues from there.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Connection, Engine

from include.db import load_sql
from include.strava.time_fields import utc_start

PROVIDER = "strava"
SOURCE = "strava"
LOOKBACK = timedelta(days=7)
# Strava returns the same access token while more than one hour is left, so refreshing
# earlier than that gains nothing.
REFRESH_MARGIN = timedelta(hours=1)
# Strava read limit is 100 requests per 15 minutes; 50 details per run leaves headroom.
DETAIL_FETCH_CAP = 50
PAGE_SIZE = 100
# Location data we never use, dropped before landing (DECISIONS D24): the route map,
# start/end coordinates, and segment efforts (each segment carries coordinates and a city).
# The one exception to "raw is stored exactly as received".
LOCATION_FIELDS = ("map", "start_latlng", "end_latlng", "segment_efforts")


@dataclass
class SyncResult:
    listed: int  # activities in the list window
    written: int  # activities fetched and upserted this run
    hit_cap: bool  # True when more remain for the next run


def save_tokens(conn: Connection, tokens: dict) -> None:
    conn.execute(
        load_sql("ops/upsert_token.sql"),
        {
            "provider": PROVIDER,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "expires_at": datetime.fromtimestamp(tokens["expires_at"], UTC),
            "scope": tokens.get("scope"),
        },
    )


def ensure_fresh_token(engine: Engine, client, now: datetime) -> None:
    """Refresh the stored access token if it expires within the hour."""
    with engine.begin() as conn:
        row = conn.execute(load_sql("ops/get_token.sql"), {"provider": PROVIDER}).one_or_none()
        if row is None:
            raise RuntimeError("No Strava token stored. Run `make strava-auth` once.")
        if row.expires_at - now > REFRESH_MARGIN:
            return
        save_tokens(conn, client.refresh(row.refresh_token))


def window_start(watermark: datetime | None, now: datetime, backfill_days: int) -> datetime:
    """First run: go back `backfill_days`. Later runs: watermark minus the lookback."""
    if watermark is None:
        return now - timedelta(days=backfill_days)
    return watermark - LOOKBACK


def list_since(client, access_token: str, after: datetime) -> list[dict]:
    """All activity summaries after `after`, oldest first, following pagination."""
    summaries: list[dict] = []
    page = 1
    while True:
        batch = client.list_activities(access_token, int(after.timestamp()), page, PAGE_SIZE)
        summaries.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    return sorted(summaries, key=utc_start)


def without_location(activity: dict) -> dict:
    """The same activity with LOCATION_FIELDS removed."""
    return {key: value for key, value in activity.items() if key not in LOCATION_FIELDS}


def new_before_loaded(engine: Engine, summaries: list[dict]) -> list[dict]:
    """Same summaries, reordered: not-yet-loaded first, then already loaded (each oldest first)."""
    with engine.connect() as conn:
        rows = conn.execute(
            load_sql("strava/loaded_ids.sql"), {"ids": [s["id"] for s in summaries]}
        )
        loaded = {row.strava_id for row in rows}
    new = [s for s in summaries if s["id"] not in loaded]
    already_loaded = [s for s in summaries if s["id"] in loaded]
    # Safe for the watermark: loaded activities are only reached after every new one fit
    # under the cap, so refreshing them can never skip past an activity not yet fetched.
    return new + already_loaded


def sync_activities(
    engine: Engine,
    client,
    now: datetime,
    backfill_days: int,
    detail_cap: int = DETAIL_FETCH_CAP,
) -> SyncResult:
    with engine.connect() as conn:
        access_token = (
            conn.execute(load_sql("ops/get_token.sql"), {"provider": PROVIDER}).one().access_token
        )
    return sync_with_token(engine, client, access_token, now, backfill_days, detail_cap)


def sync_with_token(
    engine: Engine,
    client,
    access_token: str | None,
    now: datetime,
    backfill_days: int,
    detail_cap: int = DETAIL_FETCH_CAP,
) -> SyncResult:
    """Steps 1-4 above, with the token already in hand. The public demo calls this with
    its synthetic client and no token at all (DECISIONS D119): everything after the token
    lookup is the same code the hourly DAG runs."""
    with engine.connect() as conn:
        watermark = conn.execute(
            load_sql("ops/get_watermark.sql"), {"source": SOURCE}
        ).scalar_one_or_none()

    summaries = list_since(client, access_token, window_start(watermark, now, backfill_days))
    to_fetch = new_before_loaded(engine, summaries)

    written = 0
    for summary in to_fetch[:detail_cap]:
        detail = client.get_activity(access_token, summary["id"])
        # One transaction per activity: the row and the watermark move together.
        with engine.begin() as conn:
            conn.execute(
                load_sql("strava/upsert_activity.sql"),
                {
                    "strava_id": detail["id"],
                    "payload": json.dumps(without_location(detail)),
                    "fetched_at": now,
                },
            )
            conn.execute(
                load_sql("ops/advance_watermark.sql"),
                {"source": SOURCE, "value": utc_start(detail)},
            )
        written += 1

    return SyncResult(listed=len(summaries), written=written, hit_cap=len(summaries) > detail_cap)
