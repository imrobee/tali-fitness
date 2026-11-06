"""Synthetic training, food and weigh-ins for the demo, as raw source payloads (D119).

Pure Python, no database. A scenario is:
- the days: what was trained and eaten, counted back from `today`;
- the raw payloads the two sources would send: Strava activity details (Hevy text for
  lifting sessions) and iOS Shortcut batches, shaped like the samples in docs/samples/;
- a timeline of pipeline events (a Shortcut push, a Strava sync, a data-quality run),
  which demo/replay.py runs through the real pipeline code in order.

Every value is invented. Days are counted back from `today` and never depend on the
weekday, so the streak and the other headline numbers are the same whatever date the
demo is built on. Small variations come from one random generator with a fixed seed.
"""

import copy
import json
import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SEED = 2026
TIMEZONE = "Asia/Manila"
TZ = ZoneInfo(TIMEZONE)
STRAVA_TIMEZONE = "(GMT+08:00) Asia/Manila"  # as Strava writes it (docs/samples)
FIRST_ACTIVITY_ID = 9_000_000_001  # far from real Strava ids
TARGET = {"budget": 1850, "protein": 130}
WEIGHT_GOAL_KG = 73.0
WINDOW_DAYS = 36  # the demo covers today and the 35 days before it


# --- what a day holds ---------------------------------------------------------------------


@dataclass(frozen=True)
class Activity:
    sport: str  # Strava sport_type: Run, Walk or WeightTraining
    title: str
    start: time  # local time of day
    minutes: int
    description: str | None = None  # Hevy text for WeightTraining, else None


# When the day's food is logged, and each entry's share of the day: (local time, share).
MEALS = (("08:00", 0.25), ("12:30", 0.35), ("16:00", 0.10), ("19:00", 0.30))


@dataclass
class Day:
    activities: list[Activity] = field(default_factory=list)
    food: tuple[int, int] | None = None  # (kcal, protein grams) for the whole day
    weight_kg: float | None = None  # a morning weigh-in
    meals: tuple[tuple[str, float], ...] = MEALS


@dataclass(frozen=True)
class Event:
    """One thing the pipeline did, at a moment in the demo's past.

    kind: "health" (a Shortcut push covering `day` and the day before), "strava" (an
    hourly sync), or "dq" (a data-quality run). fail: the sync's first detail call times
    out. resend: the same push arrives twice (the duplicate check absorbs it)."""

    at: datetime
    kind: str
    day: date | None = None
    fail: bool = False
    resend: bool = False


@dataclass
class Scenario:
    name: str
    today: date
    now: datetime
    nickname: str | None
    target: dict | None
    weight_goal_kg: float | None
    recovery: list[date]
    days: dict[date, Day]
    events: list[Event]

    def activities(self) -> list[dict]:
        """Every activity as a Strava detail payload, oldest first, with fixed ids."""
        details = []
        for day in sorted(self.days):
            for activity in self.days[day].activities:
                activity_id = FIRST_ACTIVITY_ID + len(details)
                details.append(strava_detail(activity_id, day, activity))
        return details


# --- Hevy text, as the Hevy app writes it into the Strava description ---------------------


def hevy_text(exercises: list[tuple[str, str | None, list[str]]]) -> str:
    """exercises: (header, note or None, set lines). Lines exactly as in docs/samples."""
    lines = ["Logged with hevyapp.com"]
    for header, note, sets in exercises:
        lines.append(header)
        if note:
            lines.append(f'"{note}"')
        lines.extend(f"Set {n}: {text}" for n, text in enumerate(sets, start=1))
    return "\n".join(lines)


def kg_x(value: float) -> str:
    return f"{value:g} kg x"


def upper_body(session: int, extra: list | None = None) -> str:
    """Session `session` (0 = the first in the window): a little heavier each time, so the
    personal records card has records to show. Every exercise is in the muscle map."""
    bench, row_lb = 17.5 + 1.25 * session, 70 + 5 * session
    exercises = [
        (
            "Incline Bench Press (Dumbbell)",
            None,
            [f"{kg_x(bench)} 10", f"{kg_x(bench)} 8", f"{kg_x(bench)} 8"],
        ),
        ("Lat Pulldown (Cable)", "Squeeze at the bottom", [f"{row_lb:g} lbs x 12"] * 3),
        ("Lateral Raise (Dumbbell)", None, [f"{kg_x(6 + 0.5 * (session // 2))} 12"] * 3),
        ("Triceps Rope Pushdown (Cable)", None, [f"{kg_x(15 + 1.25 * (session // 2))} 12"] * 3),
        ("Preacher Curl (Barbell)", None, [f"{kg_x(15 + 1.25 * (session // 2))} 10"] * 3),
    ]
    return hevy_text(exercises + (extra or []))


def lower_body(session: int) -> str:
    """Four exercises: the tour opens one of these sessions, and on a 375x812 phone it must
    fit on screen beside the tour's sheet, sets and all."""
    press = 80 + 5 * session
    exercises = [
        ("Leg Press (Machine)", None, [f"{kg_x(press)} 10"] * 3),
        ("Goblet Squat (Kettlebell)", None, [f"{kg_x(16 + 2 * (session // 2))} 12"] * 3),
        ("Lying Leg Curl (Machine)", None, [f"{kg_x(25 + 2.5 * (session // 2))} 12"] * 3),
        ("Plank", None, ["1min 0s", "1min 0s", "1min 15s"]),
    ]
    return hevy_text(exercises)


# The realistic mess, all in one session 14 days ago (the Data and sync panel's story).
# Ordinary Hevy text the real parser cannot read: it quarantines those lines, with a
# reason, and loads the rest of the session.
MESS = [
    ("Cable Core Pallof Press (Cable)", None, ["10 kg x 12", "10 kg x 12 @ RPE 8"]),
    ("Rowing (Machine)", None, ["1.5km - 8min"]),  # whole kilometres only: the header is left empty
]


# --- the days -----------------------------------------------------------------------------


def run(title: str, start: str, minutes: int) -> Activity:
    return Activity("Run", title, time.fromisoformat(start), minutes)


def lift(title: str, start: str, minutes: int, text: str) -> Activity:
    return Activity("WeightTraining", title, time.fromisoformat(start), minutes, text)


# The story, in days before today (DECISIONS D124). Three streaks: days 35 to 20 (16 days,
# the best), 18 to 11 (8 days), and 9 to today (10 with today's run and meals, 9 before
# them). Days 19 and 10 have nothing logged, which is what ends a streak.
MISSED = {19, 10}
REST = {33, 30, 27, 24, 21, 16, 13, 7, 1}  # food logged, no workout: a rest day
RECOVERY = 3  # a logged recovery day: no workout, food within budget
OVER_BUDGET = 5  # one day over budget (allowed once)
TWO_SESSIONS = 6  # a run in the morning and lifting in the evening
LIFTS = [34, 31, 28, 25, 22, 17, 14, 8, 6, 2]  # alternate upper and lower body
MESSY_LIFT = 14


def natural_meals(rng: random.Random) -> tuple[tuple[str, float], ...]:
    """A real person's day of logging: three to five entries at slightly different times
    each day, not the same four every day (the shares still add up to the whole day)."""
    plans = (
        (("07:40", 0.30), ("13:10", 0.40), ("19:45", 0.30)),
        (("08:15", 0.20), ("12:20", 0.30), ("15:30", 0.15), ("19:10", 0.35)),
        (("09:30", 0.35), ("14:00", 0.30), ("20:30", 0.35)),
        (("07:05", 0.20), ("10:30", 0.10), ("12:45", 0.30), ("16:15", 0.10), ("19:30", 0.30)),
    )
    return plans[rng.randrange(len(plans))]


def workout(n: int, rng: random.Random) -> list[Activity]:
    """What day `n` ago held: a lifting session, a run, or both."""
    if n in MISSED or n in REST or n == RECOVERY:
        return []
    if n in LIFTS:
        session = LIFTS.index(n)
        extra = MESS if n == MESSY_LIFT else None
        text = upper_body(session, extra) if session % 2 == 0 else lower_body(session)
        title = "Upper Body" if session % 2 == 0 else "Lower Body"
        start = "18:20" if n == TWO_SESSIONS else rng.choice(["07:30", "12:15", "18:40"])
        session_lift = lift(title, start, 55 + rng.randint(0, 15), text)
        if n == TWO_SESSIONS:
            return [run("Morning Run", "06:20", 30), session_lift]
        return [session_lift]
    title, start = rng.choice(
        [
            ("Morning Run", "06:15"),
            ("Easy Run", "18:30"),
            ("Tempo Run", "06:40"),
            ("Lunch Run", "12:10"),
        ]
    )
    return [run(title, start, 25 + rng.randint(0, 20))]


def tour_days(today: date, rng: random.Random) -> dict[date, Day]:
    """The public demo: 36 days ending today, built back from today (no weekday matters,
    so the story is the same on any date)."""
    days = {}
    for n in range(WINDOW_DAYS - 1, 0, -1):
        if n in MISSED:
            days[today - timedelta(days=n)] = Day()
            continue
        if n == OVER_BUDGET:
            food = (2240, 128)
        else:
            food = (1610 + rng.randint(0, 210), 112 + rng.randint(0, 26))
        weigh_in = None if n % 5 == 4 else round(74.6 - (35 - n) * 0.03 + rng.uniform(-0.2, 0.2), 1)
        days[today - timedelta(days=n)] = Day(workout(n, rng), food, weigh_in, natural_meals(rng))
    # Today, so far: a morning run and the morning's meals (only those before "now" are
    # ever synced or pushed).
    days[today] = Day(
        [run("Morning Run", "06:40", 34)],
        (1780, 126),
        74.0,
        (("07:30", 0.25), ("12:30", 0.35), ("16:00", 0.10), ("19:30", 0.30)),
    )
    return days


# --- the timeline -------------------------------------------------------------------------


def at(day: date, hhmm: str) -> datetime:
    return datetime.combine(day, time.fromisoformat(hhmm), TZ)


def tour_events(today: date, now: datetime) -> list[Event]:
    """How the data arrived, with no failures (Rob, 2026-11-05). The Shortcut pushes every
    evening, one push arrives twice (the duplicate check absorbs it), Strava syncs every
    evening, and the data-quality checks run every evening of the last week."""
    events = []
    for n in range(WINDOW_DAYS - 1, 0, -1):
        day = today - timedelta(days=n)
        events.append(Event(at(day, "21:30"), "health", day, resend=(n == 4)))
        events.append(Event(at(day, "22:00"), "strava"))
        if n <= 7:
            events.append(Event(at(day, "23:00"), "dq"))
    events += today_events(today, now)
    return sorted(events, key=lambda event: event.at)


def today_events(today: date, now: datetime) -> list[Event]:
    """Today's push, sync and checks shortly before `now` (only those already today)."""
    planned = [
        Event(now - timedelta(minutes=55), "health", today),
        Event(now - timedelta(minutes=42), "strava"),
        Event(now - timedelta(minutes=30), "dq"),
    ]
    return [event for event in planned if event.at.astimezone(TZ).date() == today]


# --- the scenarios ------------------------------------------------------------------------


def build(name: str, now: datetime) -> Scenario:
    """The scenario `name` as of `now` (an aware datetime)."""
    today = now.astimezone(TZ).date()
    rng = random.Random(SEED)
    if name == "midweek":
        return Scenario(
            "midweek", today, now, "Taiki", TARGET, WEIGHT_GOAL_KG,
            recovery=[today - timedelta(days=RECOVERY)],
            days=tour_days(today, rng),
            events=tour_events(today, now),
        )  # fmt: skip
    if name == "at_risk":
        return at_risk(today, now)
    if name == "edge_empty":
        return edge_empty(today, now)
    raise ValueError(f"Unknown scenario {name!r}. Choose one of: {', '.join(SCENARIOS)}.")


def steady(today: date, first: int, last: int) -> dict[date, Day]:
    """A run and a normal day of food on every day from `first` to `last` days ago."""
    return {
        today - timedelta(days=n): Day(
            [run("Morning Run", "06:30", 32 + n % 3 * 7)], (1640 + n * 23, 118)
        )
        for n in range(first, last - 1, -1)
    }


def at_risk(today: date, now: datetime) -> Scenario:
    """Nothing yesterday or today yet, so the streak is at risk; the last sync failed."""
    days = steady(today, 9, 2)
    events = [Event(at(day, "21:30"), "health", day) for day in sorted(days)]
    events += [Event(at(day, "22:00"), "strava") for day in sorted(days)]
    events += [
        Event(now - timedelta(hours=9), "strava"),
        Event(now - timedelta(hours=2), "strava", fail=True),
        Event(now - timedelta(minutes=30), "dq"),
    ]
    return Scenario(
        "at_risk", today, now, "Taiki", TARGET, WEIGHT_GOAL_KG, [], days,
        sorted(events, key=lambda event: event.at),
    )  # fmt: skip


def edge_empty(today: date, now: datetime) -> Scenario:
    """No targets and nothing this week: an older three-day streak, and stale sources."""
    days = steady(today, 27, 25)
    events = [Event(at(day, "21:30"), "health", day) for day in sorted(days)]
    events += [Event(at(day, "22:00"), "strava") for day in sorted(days)]
    events += [Event(now - timedelta(minutes=30), "dq")]
    return Scenario(
        "edge_empty", today, now, None, None, None, [], days,
        sorted(events, key=lambda event: event.at),
    )  # fmt: skip


SCENARIOS = ("midweek", "at_risk", "edge_empty")


# --- raw payloads, shaped like docs/samples ------------------------------------------------

KCAL_PER_MINUTE = {"Run": 10.5, "Walk": 4.5, "WeightTraining": 5.0}
HEART_RATE = {"Run": 148.0, "Walk": 104.0, "WeightTraining": 121.0}
METRES_PER_MINUTE = {"Run": 165, "Walk": 85, "WeightTraining": 0}


def strava_detail(activity_id: int, day: date, activity: Activity) -> dict:
    """A Strava activity detail. Strava writes the local start with a "Z" too."""
    local = datetime.combine(day, activity.start)
    utc = local.replace(tzinfo=TZ).astimezone(UTC)
    seconds = activity.minutes * 60
    return {
        "id": activity_id,
        "name": activity.title,
        "sport_type": activity.sport,
        "type": activity.sport,
        "start_date": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "start_date_local": local.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone": STRAVA_TIMEZONE,
        "utc_offset": 28800.0,
        "elapsed_time": seconds + 45,
        "moving_time": seconds,
        "distance": float(METRES_PER_MINUTE[activity.sport] * activity.minutes),
        "calories": round(KCAL_PER_MINUTE[activity.sport] * activity.minutes, 1),
        "average_heartrate": HEART_RATE[activity.sport],
        "has_heartrate": True,
        "description": activity.description,
        "device_name": "Apple Watch",
        "manual": False,
        "trainer": False,
        "private": False,
        "visibility": "only_me",
    }


def ended_at(detail: dict) -> datetime:
    start = datetime.strptime(detail["start_date"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return start + timedelta(seconds=detail["elapsed_time"])


class SyntheticStrava:
    """Stands in for Strava's API with the same two read calls the sync makes.

    Only activities that had ended by the sync's moment (`now`) are visible, as on the
    real Strava. `fail_next_detail` makes the next detail call time out, as Strava
    sometimes does; the real sync records that run as failed."""

    def __init__(self, details: list[dict]) -> None:
        self.details = {detail["id"]: detail for detail in details}
        self.now: datetime | None = None
        self.fail_next_detail = False

    def list_activities(
        self, access_token: str | None, after_epoch: int, page: int, per_page: int
    ) -> list[dict]:
        after = datetime.fromtimestamp(after_epoch, UTC)
        visible = [
            detail
            for detail in self.details.values()
            if ended_at(detail) <= self.now
            and datetime.strptime(detail["start_date"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            > after
        ]
        visible.sort(key=lambda detail: detail["start_date"])
        page_items = visible[(page - 1) * per_page : page * per_page]
        # Like the real list endpoint: summaries carry no description.
        return [{k: v for k, v in detail.items() if k != "description"} for detail in page_items]

    def get_activity(self, access_token: str | None, activity_id: int) -> dict:
        if self.fail_next_detail:
            self.fail_next_detail = False
            raise TimeoutError("Strava did not answer in time (demo)")
        return copy.deepcopy(self.details[activity_id])


def day_samples(day: date, plan: Day, until: datetime) -> list[dict]:
    """The Shortcut's samples for one day: a weigh-in and four meals, up to `until`."""
    samples = []
    if plan.weight_kg is not None and at(day, "07:00") <= until:
        samples.append(sample("body_mass", plan.weight_kg, "kg", at(day, "07:00")))
    if plan.food is not None:
        kcal, protein = plan.food
        for hhmm, share in plan.meals:
            if at(day, hhmm) <= until:
                samples.append(sample("dietary_energy", round(kcal * share), "kcal", at(day, hhmm)))
                samples.append(
                    sample("dietary_protein", round(protein * share, 1), "g", at(day, hhmm))
                )
    return samples


def sample(sample_type: str, value: float, unit: str, start: datetime) -> dict:
    return {
        "type": sample_type,
        "value": value,
        "unit": unit,
        "start": start.isoformat(),
        "source": "MyNetDiary",
    }


def health_body(scenario: Scenario, day: date, sent_at: datetime) -> bytes | None:
    """The Shortcut's push sent at `sent_at`: yesterday and today, as on Rob's iPhone.
    None when there is nothing to send (the real Shortcut would not push)."""
    yesterday = day - timedelta(days=1)
    samples = []
    for each in (yesterday, day):
        if each in scenario.days:
            samples += day_samples(each, scenario.days[each], sent_at)
    if not samples:
        return None
    payload = {
        "window": {"from": yesterday.isoformat(), "to": day.isoformat()},
        "device_tz": TIMEZONE,
        "samples": samples,
    }
    return json.dumps(payload).encode()
