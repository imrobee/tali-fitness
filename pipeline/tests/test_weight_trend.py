"""Body mass in core (one weight per day, the last reading wins) and the weight trend
(migration 0009, ARCHITECTURE.md 5.2, 5.5 and 14 #8)."""

from datetime import date, timedelta

from day_builder import TODAY
from sqlalchemy import Engine, text


def load_batch(engine: Engine, samples: list[tuple[str, float, str, str]]) -> str:
    """One Shortcut batch with (type, value, unit, start) samples; returns its batch_id."""
    with engine.begin() as conn:
        batch_id = conn.execute(
            text(
                "INSERT INTO raw.health_batches (window_start, window_end, device_tz, "
                "payload_sha256, payload) VALUES ('2026-01-01', '2026-12-31', 'Asia/Manila', "
                "gen_random_uuid()::text, '{}') RETURNING batch_id"
            )
        ).scalar_one()
        for idx, (sample_type, value, unit, start) in enumerate(samples):
            conn.execute(
                text(
                    "INSERT INTO raw.health_samples (batch_id, idx, type, value, unit, start_ts, "
                    "local_date, source) VALUES (:b, :i, :type, :value, :unit, "
                    "CAST(:start AS timestamptz), CAST(:local AS date), 'MyNetDiary')"
                ),
                {
                    "b": batch_id,
                    "i": idx,
                    "type": sample_type,
                    "value": value,
                    "unit": unit,
                    "start": start,
                    # The local day is the sample's own date, not a UTC conversion of it.
                    "local": start[:10],
                },
            )
        conn.execute(text("SELECT core.apply_health_batch(:b)"), {"b": batch_id})
    return batch_id


def weigh(engine: Engine, day: date, kg: float, at: str = "07:00") -> str:
    return load_batch(engine, [("body_mass", kg, "kg", f"{day}T{at}:00+08:00")])


def core_weight(engine: Engine, day: date):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT weight_kg FROM core.fact_body_mass WHERE local_date = :d"), {"d": day}
        ).scalar_one_or_none()


def set_goal(engine: Engine, effective_from: date, goal_kg: float) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO app.weight_goal_history (effective_from, goal_kg) VALUES (:d, :g)"),
            {"d": effective_from, "g": goal_kg},
        )


def trend(engine: Engine, start: date, end: date):
    with engine.connect() as conn:
        return {
            row.day: row
            for row in conn.execute(
                text("SELECT * FROM mart.fn_weight_trend(:start, :end)"),
                {"start": start, "end": end},
            )
        }


# --- core: one weight per day --------------------------------------------------------------


def test_the_last_reading_of_the_day_is_the_days_weight(engine):
    day = date(2026, 10, 20)
    load_batch(
        engine,
        [
            ("body_mass", 70.0, "kg", f"{day}T07:00:00+08:00"),
            ("body_mass", 71.5, "kg", f"{day}T19:30:00+08:00"),
            ("body_mass", 70.8, "kg", f"{day}T06:50:00+08:00"),
        ],
    )

    assert float(core_weight(engine, day)) == 71.5


def test_a_later_batch_replaces_that_days_weight(engine):
    day = date(2026, 10, 20)
    weigh(engine, day, 70.0)
    weigh(engine, day, 72.25)

    assert float(core_weight(engine, day)) == 72.25


def test_replaying_the_same_batch_changes_nothing(engine):
    day = date(2026, 10, 20)
    batch = weigh(engine, day, 74.84274105)
    with engine.begin() as conn:
        conn.execute(text("SELECT core.apply_health_batch(:b)"), {"b": batch})
        conn.execute(text("SELECT core.apply_health_batch(:b)"), {"b": batch})

    assert float(core_weight(engine, day)) == 74.84274105
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM core.fact_body_mass")).scalar_one() == 1


def test_a_batch_without_a_weight_leaves_that_day_alone(engine):
    day = date(2026, 10, 20)
    weigh(engine, day, 70.0)
    load_batch(engine, [("dietary_energy", 1500, "kcal", f"{day}T12:00:00+08:00")])

    assert float(core_weight(engine, day)) == 70.0


def test_the_full_exact_value_is_kept(engine):
    day = date(2026, 10, 20)
    weigh(engine, day, 74.84274105)

    assert str(core_weight(engine, day)) == "74.84274105"


# --- the trend -----------------------------------------------------------------------------


def test_every_day_is_listed_and_days_without_a_weight_say_so(engine):
    weigh(engine, date(2026, 10, 19), 75.0)

    days = trend(engine, date(2026, 10, 19), date(2026, 10, 21))

    assert [days[d].status for d in sorted(days)] == ["not_set", "not_logged", "not_logged"]
    assert days[date(2026, 10, 20)].weight_kg is None


def test_the_seven_day_average_uses_the_days_that_have_a_weight(engine):
    weigh(engine, date(2026, 10, 14), 76.0)
    weigh(engine, date(2026, 10, 16), 75.0)
    weigh(engine, date(2026, 10, 20), 74.0)

    row = trend(engine, date(2026, 10, 20), date(2026, 10, 20))[date(2026, 10, 20)]

    assert float(row.avg_7d_kg) == 75.0  # (76 + 75 + 74) / 3: not divided by 7


def test_the_change_compares_this_weeks_average_with_last_weeks(engine):
    for offset in range(7, 14):  # last week: 76 kg
        weigh(engine, TODAY - timedelta(days=offset), 76.0)
    for offset in range(0, 7):  # this week: 74 kg
        weigh(engine, TODAY - timedelta(days=offset), 74.0)

    row = trend(engine, TODAY, TODAY)[TODAY]

    assert float(row.change_7d_kg) == -2.0


def test_the_goal_in_effect_on_each_day_decides_its_status(engine):
    set_goal(engine, date(2026, 10, 1), 73.0)
    set_goal(engine, date(2026, 10, 15), 72.0)
    weigh(engine, date(2026, 10, 10), 72.5)  # above the goal then
    weigh(engine, date(2026, 10, 16), 72.5)  # at or below the goal now

    days = trend(engine, date(2026, 10, 10), date(2026, 10, 16))

    before = days[date(2026, 10, 10)]
    assert (before.goal_kg, before.status) == (73, "at_or_below")
    assert (days[date(2026, 10, 16)].goal_kg, days[date(2026, 10, 16)].status) == (72, "above")


def test_no_goal_set_is_not_set_and_never_judged(engine):
    weigh(engine, date(2026, 10, 20), 90.0)

    row = trend(engine, date(2026, 10, 20), date(2026, 10, 20))[date(2026, 10, 20)]

    assert (row.goal_kg, row.status) == (None, "not_set")


def test_the_six_days_before_the_range_feed_the_first_average(engine):
    weigh(engine, date(2026, 10, 14), 80.0)

    row = trend(engine, date(2026, 10, 20), date(2026, 10, 20))[date(2026, 10, 20)]

    assert float(row.avg_7d_kg) == 80.0
