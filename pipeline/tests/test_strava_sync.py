"""Strava sync against a real Postgres and a fake Strava API (PROJECT_PLAN Slice 2)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, text
from strava_fakes import FakeStrava, make_activity

from include.strava import sync
from include.strava.client import RateLimitError

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
BACKFILL_DAYS = 90


def days_ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def seed_token(engine: Engine, expires_at: datetime = NOW + timedelta(hours=5)) -> None:
    with engine.begin() as conn:
        sync.save_tokens(
            conn,
            {
                "access_token": "stored-access-token",
                "refresh_token": "stored-refresh-token",
                "expires_at": int(expires_at.timestamp()),
                "scope": "read,activity:read_all",
            },
        )


def run_sync(engine: Engine, client: FakeStrava, now: datetime = NOW, cap: int = 50):
    return sync.sync_activities(
        engine, client, now=now, backfill_days=BACKFILL_DAYS, detail_cap=cap
    )


def stored_ids(engine: Engine) -> list[int]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT strava_id FROM raw.strava_activities ORDER BY strava_id"))
        return [row.strava_id for row in rows]


def stored_description(engine: Engine, strava_id: int) -> str:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT payload->>'description' FROM raw.strava_activities WHERE strava_id = :id"),
            {"id": strava_id},
        ).scalar_one()


def watermark(engine: Engine) -> datetime | None:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT value FROM ops.watermarks WHERE source = 'strava'")
        ).scalar_one_or_none()


# --- loading and idempotency -------------------------------------------------------------


def test_first_run_loads_the_backfill_window(engine):
    seed_token(engine)
    client = FakeStrava(
        [
            make_activity(1, days_ago(1)),
            make_activity(2, days_ago(2)),
            make_activity(3, days_ago(10)),
            make_activity(4, days_ago(100)),  # older than BACKFILL_DAYS: not loaded
        ]
    )

    result = run_sync(engine, client)

    assert stored_ids(engine) == [1, 2, 3]
    assert result.written == 3
    assert not result.hit_cap
    assert watermark(engine) == days_ago(1)


def test_running_twice_creates_no_duplicates(engine):
    seed_token(engine)
    client = FakeStrava([make_activity(i, days_ago(i)) for i in (1, 2, 10)])

    run_sync(engine, client)
    run_sync(engine, client)

    assert stored_ids(engine) == [1, 2, 10]


def test_second_run_refetches_only_the_lookback_window(engine):
    seed_token(engine)
    client = FakeStrava([make_activity(i, days_ago(i)) for i in (1, 2, 10)])

    run_sync(engine, client)
    second = run_sync(engine, client)

    # Watermark is 1 day ago, so the window starts 8 days ago: activities 1 and 2 only.
    assert second.written == 2


def test_run_killed_midway_keeps_its_progress_and_the_rerun_completes(engine):
    seed_token(engine)
    activities = [make_activity(i, days_ago(i)) for i in (4, 3, 2, 1)]

    with pytest.raises(ConnectionError):
        run_sync(engine, FakeStrava(activities, fail_on_detail=3))

    # The two oldest were written (each in its own transaction) before the crash.
    assert stored_ids(engine) == [3, 4]
    assert watermark(engine) == days_ago(3)

    run_sync(engine, FakeStrava(activities))

    assert stored_ids(engine) == [1, 2, 3, 4]
    assert watermark(engine) == days_ago(1)


def test_rate_limit_stops_the_run_but_keeps_rows_already_written(engine):
    seed_token(engine)
    activities = [make_activity(i, days_ago(i)) for i in (3, 2, 1)]
    client = FakeStrava(activities, fail_on_detail=2, failure=RateLimitError("429"))

    with pytest.raises(RateLimitError):
        run_sync(engine, client)

    assert stored_ids(engine) == [3]


def test_location_data_is_never_stored(engine):
    seed_token(engine)
    run_sync(engine, FakeStrava([make_activity(1, days_ago(1))]))

    with engine.connect() as conn:
        keys = set(
            conn.execute(
                text("SELECT jsonb_object_keys(payload) FROM raw.strava_activities")
            ).scalars()
        )
    assert not keys & set(sync.LOCATION_FIELDS)
    assert {"id", "description", "start_date", "start_date_local", "sport_type"} <= keys


# --- edited descriptions and the lookback window -------------------------------------------


def test_edited_description_inside_the_lookback_is_picked_up(engine):
    seed_token(engine)
    client = FakeStrava([make_activity(1, days_ago(1)), make_activity(2, days_ago(2))])
    run_sync(engine, client)

    client.edit_description(2, "Logged with hevyapp.com\n\nEdited after upload")
    run_sync(engine, client, now=NOW + timedelta(hours=1))

    assert stored_description(engine, 2) == "Logged with hevyapp.com\n\nEdited after upload"


def test_edit_older_than_the_lookback_is_not_refetched(engine):
    # Known limitation (ARCHITECTURE.md 6.1): edits older than 7 days before the
    # newest loaded activity are not seen.
    seed_token(engine)
    client = FakeStrava([make_activity(1, days_ago(1)), make_activity(20, days_ago(20))])
    run_sync(engine, client)

    client.edit_description(20, "Edited much later")
    run_sync(engine, client, now=NOW + timedelta(hours=1))

    assert stored_description(engine, 20) == "Logged with hevyapp.com"


# --- the per-run fetch cap -----------------------------------------------------------------


def test_fetch_cap_spreads_a_backfill_over_several_runs(engine):
    seed_token(engine)
    # Five activities inside one lookback window: re-reading them must not stall the backfill.
    client = FakeStrava([make_activity(i, days_ago(i)) for i in (5, 4, 3, 2, 1)])

    first = run_sync(engine, client, cap=2)
    assert first.hit_cap
    assert stored_ids(engine) == [4, 5]

    run_sync(engine, client, cap=2)
    assert stored_ids(engine) == [2, 3, 4, 5]

    run_sync(engine, client, cap=2)
    assert stored_ids(engine) == [1, 2, 3, 4, 5]


def test_window_start_uses_backfill_first_then_watermark_minus_lookback():
    assert sync.window_start(None, NOW, BACKFILL_DAYS) == NOW - timedelta(days=90)
    assert sync.window_start(days_ago(1), NOW, BACKFILL_DAYS) == days_ago(8)


# --- tokens -------------------------------------------------------------------------------


def stored_refresh_token(engine: Engine) -> str:
    with engine.connect() as conn:
        return conn.execute(text("SELECT refresh_token FROM ops.oauth_tokens")).scalar_one()


def test_token_close_to_expiry_is_refreshed_and_the_new_refresh_token_saved(engine):
    seed_token(engine, expires_at=NOW + timedelta(minutes=30))
    client = FakeStrava([])

    sync.ensure_fresh_token(engine, client, now=NOW)

    assert client.refreshed_with == ["stored-refresh-token"]
    assert stored_refresh_token(engine) == "new-refresh-token"


def test_token_with_more_than_an_hour_left_is_not_refreshed(engine):
    seed_token(engine, expires_at=NOW + timedelta(hours=5))
    client = FakeStrava([])

    sync.ensure_fresh_token(engine, client, now=NOW)

    assert client.refreshed_with == []


def test_missing_token_says_how_to_fix_it(engine):
    with pytest.raises(RuntimeError, match="make strava-auth"):
        sync.ensure_fresh_token(engine, FakeStrava([]), now=NOW)
