"""Hevy workout text -> exercises and sets (ARCHITECTURE.md section 7).

A pure function: text in, ParsedWorkout out; no database, no Airflow. Hevy writes this
text into the Strava description, for example:

    Logged with hevyapp.com

    Incline Bench Press (Dumbbell)
    Set 1: 20 kg x 8
    Cycling
    "Training for tour de france"
    Set 1: 21km - 1h 0min

Rules: never guess and never drop silently. Any line the grammar does not know becomes a
Problem (quarantined with its line number), and the workout's status becomes 'partial'.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal

MARKER = "Logged with hevyapp.com"
KG_PER_LB = Decimal("0.45359237")
# Bump when the grammar changes: activities parsed by an older version are re-parsed
# from raw on the next run, so improvements apply to history too.
PARSER_VERSION = 2

# Duration: up to three parts in this order, e.g. "31s", "1min 30s", "10min", "1h 0min".
DURATION = r"(?:(?P<h>\d+)h)?\s*(?:(?P<min>\d+)min)?\s*(?:(?P<s>\d+)s)?"

WEIGHT_REPS = re.compile(
    r"^Set (?P<n>\d+): (?P<weight>\d+(?:\.\d+)?) (?P<unit>kg|lbs?) x (?P<reps>\d+)$",
    re.IGNORECASE,
)
REPS_ONLY = re.compile(r"^Set (?P<n>\d+): (?P<reps>\d+) reps$")
DISTANCE_DURATION = re.compile(r"^Set (?P<n>\d+): (?P<km>\d+)km - " + DURATION + "$")
DURATION_ONLY = re.compile(r"^Set (?P<n>\d+): " + DURATION + "$")
HEADER = re.compile(r"^(?P<name>.+?)(?: \((?P<equipment>[^()]+)\))?$")


@dataclass(frozen=True)
class ParsedSet:
    set_number: int
    kind: str  # weight_reps | reps | distance_duration | duration
    weight_kg: Decimal | None = None
    reps: int | None = None
    distance_m: int | None = None
    duration_s: int | None = None
    orig_weight: Decimal | None = None
    orig_unit: str | None = None  # 'kg' or 'lb'


@dataclass
class ParsedExercise:
    order: int  # position in the workout, starting at 1
    name: str
    equipment: str | None
    line_no: int  # where the header line is, for problem reports
    raw_line: str
    note: str | None = None
    sets: list[ParsedSet] = field(default_factory=list)


@dataclass(frozen=True)
class Problem:
    line_no: int  # 1-based line number in the description
    raw_content: str
    reason_code: str  # unparsed_line | empty_exercise


@dataclass
class ParsedWorkout:
    is_hevy: bool
    exercises: list[ParsedExercise]
    problems: list[Problem]

    @property
    def status(self) -> str:
        if not self.is_hevy:
            return "not_hevy"
        return "partial" if self.problems else "ok"


def seconds(match: re.Match) -> int | None:
    """Total seconds from a DURATION match, or None if no part was present."""
    hours, minutes, secs = match.group("h"), match.group("min"), match.group("s")
    if hours is None and minutes is None and secs is None:
        return None
    return int(hours or 0) * 3600 + int(minutes or 0) * 60 + int(secs or 0)


def parse_set(line: str) -> ParsedSet | None:
    """One "Set N: ..." line, or None if it matches no known set format."""
    if match := WEIGHT_REPS.match(line):
        weight = Decimal(match.group("weight"))
        unit = "lb" if match.group("unit").lower().startswith("lb") else "kg"
        weight_kg = weight * KG_PER_LB if unit == "lb" else weight
        return ParsedSet(
            int(match.group("n")),
            "weight_reps",
            weight_kg=weight_kg,
            reps=int(match.group("reps")),
            orig_weight=weight,
            orig_unit=unit,
        )
    if match := REPS_ONLY.match(line):
        return ParsedSet(int(match.group("n")), "reps", reps=int(match.group("reps")))
    if (match := DISTANCE_DURATION.match(line)) and seconds(match) is not None:
        return ParsedSet(
            int(match.group("n")),
            "distance_duration",
            distance_m=int(match.group("km")) * 1000,
            duration_s=seconds(match),
        )
    if (match := DURATION_ONLY.match(line)) and seconds(match) is not None:
        return ParsedSet(int(match.group("n")), "duration", duration_s=seconds(match))
    return None


def is_hevy(description: str | None) -> bool:
    """True when the first non-blank line is exactly the Hevy marker."""
    lines = [line.strip() for line in (description or "").splitlines() if line.strip()]
    return bool(lines) and lines[0] == MARKER


def parse_hevy(description: str | None) -> ParsedWorkout:
    if not is_hevy(description):
        return ParsedWorkout(is_hevy=False, exercises=[], problems=[])

    exercises: list[ParsedExercise] = []
    problems: list[Problem] = []
    current: ParsedExercise | None = None
    seen_marker = False

    for line_no, raw_line in enumerate(description.splitlines(), start=1):
        line = raw_line.strip()  # Strava keeps trailing spaces after each set
        if not line:
            continue
        if not seen_marker:  # the marker line itself
            seen_marker = True
            continue

        if line.startswith("Set "):
            parsed = parse_set(line)
            if parsed is None or current is None:
                problems.append(Problem(line_no, raw_line, "unparsed_line"))
            elif any(s.set_number == parsed.set_number for s in current.sets):
                problems.append(Problem(line_no, raw_line, "unparsed_line"))  # repeated number
            else:
                current.sets.append(parsed)
            continue

        is_quoted = len(line) >= 2 and line.startswith('"') and line.endswith('"')
        if is_quoted:
            # A note is only valid directly under its exercise, before the first set.
            if current is not None and not current.sets and current.note is None:
                current.note = line[1:-1]
            else:
                problems.append(Problem(line_no, raw_line, "unparsed_line"))
            continue

        # Anything else starts a new exercise: "Name" or "Name (Equipment)".
        header = HEADER.match(line)
        current = ParsedExercise(
            order=len(exercises) + 1,
            name=header.group("name").strip(),
            equipment=header.group("equipment"),
            line_no=line_no,
            raw_line=raw_line,
        )
        exercises.append(current)

    # An exercise header with no sets under it is reported, not loaded.
    for exercise in exercises:
        if not exercise.sets:
            problems.append(Problem(exercise.line_no, exercise.raw_line, "empty_exercise"))
    loaded = [exercise for exercise in exercises if exercise.sets]
    for order, exercise in enumerate(loaded, start=1):
        exercise.order = order
    return ParsedWorkout(is_hevy=True, exercises=loaded, problems=problems)
