"""Insert test days straight into core/app tables, for the dashboard and recovery tests.

The frozen clock in conftest makes "today" Tuesday 2026-10-20 (NOW_OVERRIDE).
"""

from datetime import date

from sqlalchemy import Engine, text

TODAY = date(2026, 10, 20)  # a Tuesday


def date_key(day: date) -> int:
    return day.year * 10000 + day.month * 100 + day.day


def add_activity(
    engine: Engine,
    day: date,
    sport: str = "Run",
    app_type: str = "run",
    title: str = "Afternoon Run",
    local_time: str = "17:00",
    duration_s: int = 1800,
    strava_id: int | None = None,
) -> None:
    strava_id = strava_id or date_key(day) * 10 + int(local_time[:2]) // 3
    started = f"{day}T{local_time}:00+08:00"
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO raw.strava_activities (strava_id, payload, fetched_at) "
                "VALUES (:id, '{}', now())"
            ),
            {"id": strava_id},
        )
        conn.execute(
            text(
                "INSERT INTO core.dim_activity_type (strava_sport_type, app_type, label) "
                "VALUES (:sport, :app_type, :sport) ON CONFLICT DO NOTHING"
            ),
            {"sport": sport, "app_type": app_type},
        )
        conn.execute(
            text(
                "INSERT INTO core.fact_activity (strava_id, date_key, activity_type_key, title, "
                "started_at, started_local, ended_at, tz, duration_s, source_fetched_at) "
                "SELECT :id, :date_key, activity_type_key, :title, CAST(:started AS timestamptz), "
                "CAST(:local AS timestamp), CAST(:started AS timestamptz), 'Asia/Manila', "
                ":duration, now() FROM core.dim_activity_type WHERE strava_sport_type = :sport"
            ),
            {
                "id": strava_id,
                "date_key": date_key(day),
                "title": title,
                "started": started,
                "local": f"{day} {local_time}",
                "duration": duration_s,
                "sport": sport,
            },
        )


def add_food(engine: Engine, day: date, kcal: float | None = 1500, protein: float | None = None):
    with engine.begin() as conn:
        batch_id = conn.execute(
            text(
                "INSERT INTO raw.health_batches (window_start, window_end, device_tz, "
                "payload_sha256, payload) VALUES (:day, :day, 'Asia/Manila', 'test', '{}') "
                "RETURNING batch_id"
            ),
            {"day": day},
        ).scalar_one()
        samples = [("energy", kcal), ("protein", protein)]
        for idx, (sample_type, value) in enumerate(samples):
            if value is None:
                continue
            conn.execute(
                text(
                    "INSERT INTO core.fact_dietary_sample (batch_id, sample_idx, date_key, "
                    "local_date, sample_type, value, start_ts) VALUES (:batch_id, :idx, "
                    ":date_key, :day, :type, :value, CAST(:start AS timestamptz))"
                ),
                {
                    "batch_id": batch_id,
                    "idx": idx,
                    "date_key": date_key(day),
                    "day": day,
                    "type": sample_type,
                    "value": value,
                    "start": f"{day}T12:00:00+08:00",
                },
            )


def qualify(engine: Engine, day: date) -> None:
    add_activity(engine, day)
    add_food(engine, day)


def add_recovery(engine: Engine, day: date) -> None:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app.recovery_day (day) VALUES (:day)"), {"day": day})


def add_target(engine: Engine, effective_from: date, budget: int = 1853, protein: int = 130):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO app.target_history (effective_from, calorie_budget, protein_goal) "
                "VALUES (:day, :budget, :protein)"
            ),
            {"day": effective_from, "budget": budget, "protein": protein},
        )
