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
TARGET = {"budget": 1853, "protein": 130}
WEIGHT_GOAL_KG = 73.0
HISTORY_DAYS = 165  # oldest day with data, counted back from today


# --- what a day holds ---------------------------------------------------------------------


@dataclass(frozen=True)
class Activity:
    sport: str  # Strava sport_type: Run, Walk or WeightTraining
    title: str
    start: time  # local time of day
    minutes: int
    description: str | None = None  # Hevy text for WeightTraining, else None


@dataclass
class Day:
    activities: list[Activity] = field(default_factory=list)
    food: tuple[int, int] | None = None  # (kcal, protein grams) for the whole day
    weight_kg: float | None = None  # a morning weigh-in


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


def kg(value: float) -> str:
    return f"{value:g} kg"


def upper_body(n: int, extra: list | None = None) -> str:
    """An upper-body session `n` days ago, a little heavier every three weeks, so the
    personal records card has records to show."""
    step = (HISTORY_DAYS - n) // 21
    bench, pulldown_lb, raise_kg = 15 + 1.25 * step, 30 + 2.5 * step, 5 + 0.5 * (step // 2)
    exercises = [
        ("Incline Bench Press (Dumbbell)", None, [f"{kg(bench)} x 8"] * 3),
        ("Lat Pulldown (Cable)", None, [f"{pulldown_lb:g} lbs x 12"] * 3),
        ("Lateral Raise (Dumbbell)", None, [f"{kg(raise_kg)} x 12"] * 2),
    ]
    return hevy_text(exercises + (extra or []))


# Today's session: the screenshots open it and look for "20 kg × 8".
FULL_BODY = hevy_text(
    [
        ("Incline Bench Press (Dumbbell)", None, ["20 kg x 8", "22.5 kg x 6"]),
        ("Lat Pulldown (Cable)", "Squeeze at the bottom", ["40 lbs x 12"]),
        ("Goblet Squat (Kettlebell)", None, ["15 reps"]),
        ("Plank", None, ["1min 30s"]),
    ]
)

# The realistic mess (the Data and sync panel's story). Each is ordinary Hevy text that
# the real parser cannot read; it quarantines the line and loads the rest of the session.
RPE_NOTE = ("Triceps Rope Pushdown (Cable)", None, ["15 kg x 12", "15 kg x 10 @ RPE 9"])
DECIMAL_DISTANCE = ("Rowing (Machine)", None, ["1.5km - 8min"])  # whole km only
# Not in db/seeds/exercise_muscle_map.csv: lands in the "unmapped exercises" check.
UNMAPPED = ("Landmine Press (Barbell)", None, ["20 kg x 10", "20 kg x 10"])


# --- the days -----------------------------------------------------------------------------


def run(title: str, start: str, minutes: int) -> Activity:
    return Activity("Run", title, time.fromisoformat(start), minutes)


def lift(title: str, start: str, minutes: int, text: str) -> Activity:
    return Activity("WeightTraining", title, time.fromisoformat(start), minutes, text)


def history_day(n: int, rng: random.Random) -> Day:
    """An older day, `n` days ago: about three sessions a week and food on most days."""
    activities = []
    if n % 7 in (0, 4):
        activities.append(run("Morning Run", "06:30", 28 + rng.randint(0, 12)))
    if n % 7 == 2:
        activities.append(lift("Upper Body", "17:10", 50 + rng.randint(0, 10), upper_body(n)))
    if n % 14 == 5:
        activities.append(run("Long Run", "07:00", 66 + rng.randint(0, 16)))
    food = None if n % 9 == 0 else (1690 + rng.randint(0, 380), 104 + rng.randint(0, 28))
    return Day(activities, food)


def weight_on(n: int, rng: random.Random) -> float | None:
    """A weigh-in most mornings for the last 90 days, drifting down towards the goal."""
    if n > 90 or n % 6 == 5:
        return None
    return round(74.2 + n * 0.012 + rng.uniform(-0.25, 0.25), 1)


def tour_days(today: date, rng: random.Random) -> dict[date, Day]:
    """The public demo: a 12-day streak ending today, with history behind it.

    Day 12 ago is empty, so the streak starts on day 11 ago. Inside the streak: one day
    over budget (allowed once), one logged recovery day, a day with two sessions, and
    lifting sessions carrying the mess above (one of them 37 days ago). Today has three
    activities and food logged so far (only what happened before the demo's "now" is
    ever synced)."""
    days = {today - timedelta(days=n): history_day(n, rng) for n in range(HISTORY_DAYS, 12, -1)}
    days[today - timedelta(days=12)] = Day()
    recent = {
        11: ([run("Morning Run", "06:30", 32)], (1702, 118)),
        10: ([lift("Upper Body", "17:10", 61, upper_body(10))], (1788, 131)),
        9: ([run("Morning Run", "06:30", 36)], (1645, 122)),
        8: (
            [run("Morning Run", "06:30", 30), lift("Upper Body", "17:10", 58, upper_body(8))],
            (1810, 140),
        ),
        7: ([run("Tempo Run", "06:15", 38)], (2173, 141)),  # over budget, once
        6: ([lift("Upper Body", "17:10", 64, upper_body(6, [RPE_NOTE]))], (1724, 127)),
        5: ([run("Morning Run", "06:30", 41)], (1689, 122)),
        4: ([run("Long Run", "07:00", 74)], (1835, 129)),
        3: ([], (1610, 116)),  # a logged recovery day (no workout)
        2: ([lift("Upper Body", "17:10", 57, upper_body(2, [UNMAPPED]))], (1755, 131)),
        1: ([run("Easy Run", "18:40", 29)], (1740, 126)),
    }
    for n, (activities, food) in recent.items():
        days[today - timedelta(days=n)] = Day(activities, food)
    # An older session with a line the parser can't read: still open in quarantine, but
    # outside the 30-day parse-coverage check, which warns rather than fails (D119).
    older = days[today - timedelta(days=37)]
    older.activities = [lift("Upper Body", "17:10", 55, upper_body(37, [DECIMAL_DISTANCE]))]
    days[today] = Day(
        [
            Activity("Walk", "Morning Walk", time(7, 10), 45),
            lift("Full Body", "10:30", 68, FULL_BODY),
            run("Lunch Run", "12:20", 30),
        ],
        (1180, 74),  # the whole day's plan; only meals before "now" are pushed
    )
    for day, plan in days.items():
        plan.weight_kg = weight_on((today - day).days, rng)
    return days


# --- the timeline -------------------------------------------------------------------------


def at(day: date, hhmm: str) -> datetime:
    return datetime.combine(day, time.fromisoformat(hhmm), TZ)


def tour_events(today: date, now: datetime) -> list[Event]:
    """How the data arrived. History is backfilled by Strava's first sync (two runs: the
    first stops at the 50-detail cap). The Shortcut pushes every evening; it went quiet
    for three days five weeks ago (a data-quality run flagged it, then it recovered); one
    push arrived twice; one sync timed out and its retry succeeded."""
    events = []
    quiet = {today - timedelta(days=n) for n in (40, 39, 38)}
    for n in range(HISTORY_DAYS, 0, -1):
        day = today - timedelta(days=n)
        if day not in quiet:
            events.append(Event(at(day, "21:30"), "health", day, resend=(n == 5)))
    events.append(Event(at(today - timedelta(days=38), "23:00"), "dq"))  # flags the quiet Shortcut
    events.append(Event(at(today - timedelta(days=14), "22:00"), "strava"))  # backfill, part 1
    events.append(Event(at(today - timedelta(days=14), "23:00"), "strava"))  # backfill, part 2
    for n in range(13, 0, -1):
        day = today - timedelta(days=n)
        if n == 3:
            events.append(Event(at(day, "22:00"), "strava", fail=True))
            events.append(Event(at(day, "22:30"), "strava"))  # the retry
        else:
            events.append(Event(at(day, "22:00"), "strava"))
        if n <= 6:
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
            "midweek", today, now, "Sam", TARGET, WEIGHT_GOAL_KG,
            recovery=[today - timedelta(days=3)],
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
        "at_risk", today, now, "Sam", TARGET, WEIGHT_GOAL_KG, [], days,
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


MEALS = (("08:00", 0.25), ("12:30", 0.35), ("16:00", 0.10), ("19:00", 0.30))


def day_samples(day: date, plan: Day, until: datetime) -> list[dict]:
    """The Shortcut's samples for one day: a weigh-in and four meals, up to `until`."""
    samples = []
    if plan.weight_kg is not None and at(day, "07:00") <= until:
        samples.append(sample("body_mass", plan.weight_kg, "kg", at(day, "07:00")))
    if plan.food is not None:
        kcal, protein = plan.food
        for hhmm, share in MEALS:
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
