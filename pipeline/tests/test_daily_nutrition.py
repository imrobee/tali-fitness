"""Daily calories against the target in effect that day (ARCHITECTURE.md 8.1)."""

from datetime import date

from day_builder import add_calories, add_target
from sqlalchemy import text


def nutrition(engine, start: date, end: date):
    with engine.connect() as conn:
        return {
            row.day: row
            for row in conn.execute(
                text("SELECT * FROM mart.fn_daily_nutrition(:start, :end)"),
                {"start": start, "end": end},
            )
        }


def test_every_day_in_the_range_appears_even_without_samples(engine):
    rows = nutrition(engine, date(2026, 10, 19), date(2026, 10, 21))

    assert list(rows) == [date(2026, 10, 19), date(2026, 10, 20), date(2026, 10, 21)]
    assert {row.calorie_status for row in rows.values()} == {"not_logged"}


def test_calories_without_a_budget_are_not_set_never_over(engine):
    add_calories(engine, date(2026, 10, 20), kcal=4500)

    assert (
        nutrition(engine, date(2026, 10, 20), date(2026, 10, 20))[date(2026, 10, 20)].calorie_status
        == "not_set"
    )


def test_within_and_over_compare_with_the_budget(engine):
    add_target(engine, date(2026, 10, 1), budget=1853)
    add_calories(engine, date(2026, 10, 19), kcal=1853)  # exactly the budget: within
    add_calories(engine, date(2026, 10, 20), kcal=2173)

    rows = nutrition(engine, date(2026, 10, 19), date(2026, 10, 20))

    assert rows[date(2026, 10, 19)].calorie_status == "within"
    assert rows[date(2026, 10, 20)].calorie_status == "over"
    assert rows[date(2026, 10, 20)].kcal == 2173


def test_a_budget_change_mid_week_does_not_rewrite_past_days(engine):
    add_target(engine, date(2026, 10, 1), budget=2000)
    add_target(engine, date(2026, 10, 15), budget=1500)  # edited "today" = Oct 15
    add_calories(engine, date(2026, 10, 10), kcal=1800)
    add_calories(engine, date(2026, 10, 16), kcal=1800)

    rows = nutrition(engine, date(2026, 10, 10), date(2026, 10, 16))

    assert (rows[date(2026, 10, 10)].calorie_budget, rows[date(2026, 10, 10)].calorie_status) == (
        2000,
        "within",
    )
    assert (rows[date(2026, 10, 16)].calorie_budget, rows[date(2026, 10, 16)].calorie_status) == (
        1500,
        "over",
    )


def test_protein_is_summed_per_day(engine):
    add_target(engine, date(2026, 10, 1), budget=2000, protein=130)
    with engine.begin() as conn:
        batch_id = conn.execute(
            text(
                "INSERT INTO raw.health_batches (window_start, window_end, device_tz, "
                "payload_sha256, payload) VALUES ('2026-10-20', '2026-10-20', 'Asia/Manila', "
                "'p', '{}') RETURNING batch_id"
            )
        ).scalar_one()
        for idx, grams in enumerate([20.8, 13]):
            conn.execute(
                text(
                    "INSERT INTO core.fact_dietary_sample (batch_id, sample_idx, date_key, "
                    "local_date, sample_type, value, start_ts) VALUES (:b, :i, 20261020, "
                    "'2026-10-20', 'protein', :g, now())"
                ),
                {"b": batch_id, "i": idx, "g": grams},
            )

    row = nutrition(engine, date(2026, 10, 20), date(2026, 10, 20))[date(2026, 10, 20)]

    assert (float(row.protein_g), row.protein_goal) == (33.8, 130)
