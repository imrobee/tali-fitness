"""GET /api/v1/dashboard response (ARCHITECTURE.md section 11).

The web app depends on these field names; change them only together with the UI.
"""

from datetime import date, datetime

from pydantic import BaseModel


class StreakDay(BaseModel):
    date: date
    weekday: str  # single letter, Monday first: M T W T F S S
    state: str  # qualifying | recovery | today_pending | at_risk | missed | future
    primary_activity_type: str | None  # longest activity that day; drives the icon
    calorie_status: str  # not_logged | not_set | within | over


class Streak(BaseModel):
    count: int
    at_risk: bool
    message: str | None
    week: list[StreakDay]  # always the current Monday-Sunday week


class Recovery(BaseModel):
    state: str  # available | logged | no_freeze | blocked | counted | locked
    freezes_left: int
    freezes_max: int


class Exercise(BaseModel):
    id: int
    type: str
    title: str | None
    started_at: datetime  # with the activity's own UTC offset
    duration_s: int


class Calories(BaseModel):
    eaten: int
    budget: int | None  # null when no budget is set
    remaining: int | None
    over: int | None
    status: str


class Protein(BaseModel):
    grams: int
    goal: int | None
    percent: int | None


class WeekBar(BaseModel):
    date: date
    kcal: int | None
    budget: int | None
    status: str  # also 'future' for days after today


class WeekChart(BaseModel):
    week_start: date
    bars: list[WeekBar]  # the Monday-Sunday week containing selected_date


class Dashboard(BaseModel):
    today: date
    selected_date: date
    earliest_date: date
    greeting: str
    nickname: str | None
    streak: Streak
    recovery: Recovery
    exercises: list[Exercise]
    calories: Calories
    protein: Protein
    week_chart: WeekChart
