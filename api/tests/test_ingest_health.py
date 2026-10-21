"""POST /api/v1/ingest/health against a real Postgres (PROJECT_PLAN Slice 3 acceptance).

health_payload_01.json is a real day; _02.json is the same day after one entry was
edited (576 -> 504 kcal, 20.8 -> 18.2 g) and one deleted (172 kcal, 4.8 g).
"""

import json

import pytest
from conftest import TEST_API_KEY, load_sample
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ingest import store

URL = "/api/v1/ingest/health"
HEADERS = {"X-API-Key": TEST_API_KEY}


def post(client: TestClient, payload: dict, headers: dict | None = None):
    return client.post(URL, content=json.dumps(payload), headers=headers or HEADERS)


def day_totals(engine: Engine, day: str = "2026-10-20") -> dict[str, float]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT sample_type, sum(value) AS total FROM core.fact_dietary_sample "
                "WHERE local_date = :day GROUP BY sample_type"
            ),
            {"day": day},
        )
        return {row.sample_type: float(row.total) for row in rows}


def count(engine: Engine, table: str) -> int:
    queries = {
        "batches": "SELECT count(*) FROM raw.health_batches",
        "samples": "SELECT count(*) FROM raw.health_samples",
        "facts": "SELECT count(*) FROM core.fact_dietary_sample",
        "quarantine": "SELECT count(*) FROM ops.quarantine",
        "runs": "SELECT count(*) FROM ops.pipeline_runs",
    }
    with engine.connect() as conn:
        return conn.execute(text(queries[table])).scalar_one()


# --- auth and request-level errors ---------------------------------------------------------


def test_missing_api_key_is_401(client):
    response = client.post(URL, content=json.dumps(load_sample("health_payload_01.json")))

    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "unauthorized", "message": "Missing or wrong X-API-Key header."}
    }


def test_wrong_api_key_is_401(client):
    response = post(client, load_sample("health_payload_01.json"), {"X-API-Key": "wrong"})

    assert response.status_code == 401


def test_empty_batch_is_422_and_stores_nothing(client, engine):
    payload = load_sample("health_payload_01.json")
    payload["samples"] = []

    response = post(client, payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_batch"
    assert count(engine, "batches") == 0


def test_body_that_is_not_json_is_invalid_payload(client):
    response = client.post(URL, content=b"not json", headers=HEADERS)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_payload"


def test_samples_sent_as_one_string_are_invalid_payload(client):
    # What the Shortcut first sent in the Slice 0 spike.
    payload = load_sample("health_payload_01.json")
    payload["samples"] = [json.dumps(payload["samples"])]

    response = post(client, payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_payload"


def test_window_ending_after_tomorrow_is_date_out_of_range(client):
    payload = load_sample("health_payload_01.json")
    payload["window"] = {"from": "2026-10-20", "to": "2026-10-22"}  # frozen today: Oct 20

    response = post(client, payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "date_out_of_range"


def test_unknown_device_time_zone_is_invalid_payload(client):
    payload = load_sample("health_payload_01.json")
    payload["device_tz"] = "Mars/Olympus"

    assert post(client, payload).json()["error"]["code"] == "invalid_payload"


def test_body_over_1_mb_is_413(client):
    response = client.post(URL, content=b"x" * 1_000_001, headers=HEADERS)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


# --- landing and applying a batch ----------------------------------------------------------


def test_real_payload_lands_in_raw_and_core(client, engine):
    response = post(client, load_sample("health_payload_01.json"))

    assert response.status_code == 201
    body = response.json()
    assert (body["received"], body["accepted"], body["rejected"]) == (11, 11, 0)
    assert body["duplicate"] is False
    assert day_totals(engine) == {"energy": 1575.0, "protein": 63.6}
    # Body mass lands in raw only; core.fact_dietary_sample is dietary.
    assert count(engine, "samples") == 11
    assert count(engine, "facts") == 10


def test_same_payload_twice_is_a_duplicate_and_changes_nothing(client, engine):
    first = post(client, load_sample("health_payload_01.json")).json()
    second = post(client, load_sample("health_payload_01.json"))

    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["batch_id"] == first["batch_id"]
    assert count(engine, "batches") == 1
    assert day_totals(engine) == {"energy": 1575.0, "protein": 63.6}
    # Both requests are logged, so freshness checks can see the Shortcut is alive.
    assert count(engine, "runs") == 2


def test_same_samples_in_a_different_order_are_still_a_duplicate(client, engine):
    # The Shortcut returns samples in a new order on each run (live, 2026-10-21).
    payload = load_sample("health_payload_01.json")
    post(client, payload)
    payload["samples"] = list(reversed(payload["samples"]))

    response = post(client, payload)

    assert response.json()["duplicate"] is True
    assert count(engine, "batches") == 1


def test_edited_and_deleted_entries_update_the_day(client, engine):
    post(client, load_sample("health_payload_01.json"))
    response = post(client, load_sample("health_payload_02.json"))

    assert response.status_code == 201
    assert day_totals(engine) == {"energy": 1331.0, "protein": 56.2}


def test_a_type_missing_from_a_batch_leaves_that_types_rows_untouched(client, engine):
    post(client, load_sample("health_payload_01.json"))
    energy_only = load_sample("health_payload_02.json")
    energy_only["samples"] = [s for s in energy_only["samples"] if s["type"] == "dietary_energy"]

    post(client, energy_only)

    # Energy replaced from the new batch; protein kept from the first one.
    assert day_totals(engine) == {"energy": 1331.0, "protein": 63.6}


def test_a_day_outside_the_new_batch_is_untouched(client, engine):
    post(client, load_sample("health_payload_01.json"))
    yesterday_only = load_sample("health_payload_01.json")
    yesterday_only["samples"] = [
        {**s, "start": "2026-10-19T09:00:00+08:00"} for s in yesterday_only["samples"][:2]
    ]

    post(client, yesterday_only)

    assert day_totals(engine) == {"energy": 1575.0, "protein": 63.6}
    assert day_totals(engine, "2026-10-19") == {"energy": 1176.0}


def test_invalid_samples_are_quarantined_and_the_rest_accepted(client, engine):
    payload = load_sample("health_payload_01.json")
    payload["samples"].append(
        {"type": "body_mass", "value": 160, "unit": "lb", "start": "2026-10-20T07:00:00+08:00"}
    )

    body = post(client, payload).json()

    assert (body["received"], body["accepted"], body["rejected"]) == (12, 11, 1)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM ops.quarantine")).one()
    assert row.source == "health"
    assert row.reason_code == "bad_unit"
    assert row.line_no == 11
    assert json.loads(row.raw_content)["unit"] == "lb"
    assert day_totals(engine) == {"energy": 1575.0, "protein": 63.6}


def test_the_run_is_logged_with_counts(client, engine):
    payload = load_sample("health_payload_01.json")
    payload["samples"].append(
        {
            "type": "dietary_energy",
            "value": -5,
            "unit": "kcal",
            "start": "2026-10-20T08:00:00+08:00",
        }
    )
    post(client, payload)

    with engine.connect() as conn:
        run = conn.execute(text("SELECT * FROM ops.pipeline_runs")).one()
    assert run.source == "health"
    assert run.status == "success"
    assert (run.rows_read, run.rows_written, run.rows_quarantined) == (12, 11, 1)


def test_a_failure_mid_batch_rolls_back_raw_and_core(engine, monkeypatch):
    def broken_apply(conn, batch_id):
        raise RuntimeError("simulated failure after raw rows were written")

    monkeypatch.setattr(store, "apply_batch", broken_apply)
    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    from app.db import get_engine
    from app.main import app

    app.dependency_overrides[get_engine] = lambda: engine
    try:
        with pytest.raises(RuntimeError, match="simulated failure"):
            TestClient(app).post(
                URL, content=json.dumps(load_sample("health_payload_01.json")), headers=HEADERS
            )
    finally:
        app.dependency_overrides.clear()

    for table in ("batches", "samples", "facts", "quarantine", "runs"):
        assert count(engine, table) == 0, table


def test_the_database_rejects_an_impossible_calorie_value(engine):
    # Rules live in the database too (CLAUDE.md conventions), not only in Python.
    with pytest.raises(Exception, match="check"), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO raw.health_batches (window_start, window_end, device_tz, "
                "payload_sha256, payload) VALUES ('2026-10-20', '2026-10-20', 'Asia/Manila', "
                "'x', '{}') RETURNING batch_id"
            )
        )
        conn.execute(
            text(
                "INSERT INTO core.fact_dietary_sample (batch_id, sample_idx, date_key, "
                "local_date, sample_type, value, start_ts) SELECT batch_id, 0, 20261020, "
                "'2026-10-20', 'energy', 99999, now() FROM raw.health_batches"
            )
        )
