"""Build test days straight into core/app tables, for the business-rule tests.

Notation from ARCHITECTURE.md 8.4, oldest to newest, the last item is today:
  Q  qualifying (workout + calories)    R   recovery day logged
  M  nothing                            A   workout only
  C  calories only                      T   today, nothing yet
  Tq today qualifying                   Rq  recovery logged on a day that also qualifies
  Qo qualifying, over the budget        R(today)  recovery logged today
"""

from datetime import date, timedelta

from sqlalchemy import Engine, text

TODAY = date(2026, 10, 21)

TOKENS = {
    #            activity, calories, recovery
    "Q": (True, True, False),
    "Qo": (True, True, False),  # same flags; tests add a budget below its calories
    "R": (False, False, True),
    "M": (False, False, False),
    "A": (True, False, False),
    "C": (False, True, False),
    "T": (False, False, False),
    "Tq": (True, True, False),
    "Rq": (True, True, True),
    "R(today)": (False, False, True),
}


def date_key(day: date) -> int:
    return day.year * 10000 + day.month * 100 + day.day


def add_activity(engine: Engine, day: date) -> None:
    strava_id = date_key(day)  # one activity per day is enough here
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
                "VALUES ('Run', 'run', 'Run') ON CONFLICT DO NOTHING"
            )
        )
        conn.execute(
            text(
                "INSERT INTO core.fact_activity (strava_id, date_key, activity_type_key, "
                "started_at, started_local, ended_at, duration_s, source_fetched_at) "
                "SELECT :id, :date_key, activity_type_key, CAST(:started_at AS timestamptz), "
                "CAST(:started_local AS timestamp), CAST(:started_at AS timestamptz), 1800, now() "
                "FROM core.dim_activity_type WHERE strava_sport_type = 'Run'"
            ),
            {
                "id": strava_id,
                "date_key": date_key(day),
                "started_at": f"{day}T08:00:00+08:00",
                "started_local": f"{day} 08:00",
            },
        )


def add_calories(engine: Engine, day: date, kcal: float = 1500, at: str = "12:00") -> None:
    with engine.begin() as conn:
        batch_id = conn.execute(
            text(
                "INSERT INTO raw.health_batches (window_start, window_end, device_tz, "
                "payload_sha256, payload) VALUES (:day, :day, 'Asia/Manila', 'test', '{}') "
                "RETURNING batch_id"
            ),
            {"day": day},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO core.fact_dietary_sample (batch_id, sample_idx, date_key, "
                "local_date, sample_type, value, start_ts) "
                "VALUES (:batch_id, 0, :date_key, :day, 'energy', :kcal, "
                "CAST(:start AS timestamptz))"
            ),
            {
                "batch_id": batch_id,
                "date_key": date_key(day),
                "day": day,
                "kcal": kcal,
                "start": f"{day}T{at}:00+08:00",
            },
        )


def add_recovery(engine: Engine, day: date) -> None:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app.recovery_day (day) VALUES (:day)"), {"day": day})


def add_target(engine: Engine, effective_from: date, budget: int, protein: int = 130) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO app.target_history (effective_from, calorie_budget, protein_goal) "
                "VALUES (:day, :budget, :protein)"
            ),
            {"day": effective_from, "budget": budget, "protein": protein},
        )


def build(engine: Engine, sequence: str, today: date = TODAY) -> list[date]:
    """Insert a sequence like "Q R Q T" ending on `today`. Returns the dates used."""
    tokens = sequence.split()
    days = [today - timedelta(days=len(tokens) - 1 - i) for i in range(len(tokens))]
    for token, day in zip(tokens, days, strict=True):
        activity, calories, recovery = TOKENS[token]
        if activity:
            add_activity(engine, day)
        if calories:
            add_calories(engine, day, kcal=2500 if token == "Qo" else 1500)
        if recovery:
            add_recovery(engine, day)
    return days


def streak(engine: Engine, today: date = TODAY):
    with engine.connect() as conn:
        return conn.execute(text("SELECT * FROM mart.fn_streak(:today)"), {"today": today}).one()


def states(engine: Engine, today: date = TODAY) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT state FROM mart.fn_day_status(:today)"), {"today": today})
        return [row.state for row in rows]
