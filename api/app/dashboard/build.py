"""Builds the dashboard payload from the mart functions.

The rules (day states, streak, recovery card, calorie status) are computed in SQL; this
module only gathers them for one selected day and adds display text (greeting, message).
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Connection

from app.dashboard.models import (
    Calories,
    Dashboard,
    Exercise,
    Protein,
    Recovery,
    Streak,
    StreakDay,
    WeekBar,
    WeekChart,
)
from app.db import load_sql
from app.errors import ApiError

WEEKDAY_LETTERS = "MTWTFSS"


def greeting(now_local: datetime) -> str:
    """05:00-11:59 morning, 12:00-17:59 afternoon, otherwise evening (ARCHITECTURE.md 4)."""
    if 5 <= now_local.hour < 12:
        return "Good morning"
    if 12 <= now_local.hour < 18:
        return "Good afternoon"
    return "Good evening"


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_of(day: date) -> list[date]:
    start = monday_of(day)
    return [start + timedelta(days=i) for i in range(7)]


def best_streak(days) -> int:
    """The longest chain so far: most counted days in any one island."""
    per_island: dict[int, int] = {}
    for day in days:
        if day.counted:
            per_island[day.island_id] = per_island.get(day.island_id, 0) + 1
    return max(per_island.values(), default=0)


def streak_message(streak, best: int) -> str | None:
    """Quiet one-line copy for the streak card (UI_SPEC.md section 9), from fn_streak."""
    count = streak.streak
    if streak.at_risk:
        keep = f"to keep your {count}-day streak."
        if streak.yesterday_kind == "recovery":
            return f"Yesterday was a second rest day in a row. Log its workout {keep}"
        if streak.yesterday_kind == "over":
            return f"Yesterday was a second day over budget. Check its food log {keep}"
        return f"Yesterday isn't logged. Fill it in to keep your {count}-day streak."
    if streak.today_state == "pending" and streak.today_kind == "recovery":
        return "Yesterday was a rest day. A workout today keeps your streak going."
    if streak.today_state == "pending" and streak.today_kind == "over":
        return "Yesterday was over budget too. Staying within it today keeps your streak going."
    if streak.today_state == "counted":
        return "Nice. Today's counted."
    if count == 0 and best > 0:
        return f"Fresh start today. Your best was {best} days."
    return None


def nutrition_by_day(conn: Connection, start: date, end: date) -> dict:
    rows = conn.execute(load_sql("api/daily_nutrition.sql"), {"start": start, "end": end})
    return {row.day: row for row in rows}


def calories_card(row) -> Calories:
    eaten = round(row.kcal or 0)
    budget = row.calorie_budget if row.calorie_status != "not_set" else None
    if budget is None:
        return Calories(
            eaten=eaten, budget=None, remaining=None, over=None, status=row.calorie_status
        )
    return Calories(
        eaten=eaten,
        budget=budget,
        remaining=max(budget - eaten, 0),
        over=max(eaten - budget, 0),
        status=row.calorie_status,
    )


def protein_card(row) -> Protein:
    grams = round(row.protein_g or 0)
    goal = row.protein_goal
    percent = round(100 * grams / goal) if goal else None
    return Protein(grams=grams, goal=goal, percent=percent)


def build_dashboard(
    conn: Connection, today: date, now_local: datetime, selected: date
) -> Dashboard:
    days = conn.execute(load_sql("api/day_status.sql"), {"today": today}).all()
    status_by_day = {row.day: row for row in days}
    earliest = days[0].day if days else today
    if selected > today or selected < earliest:
        raise ApiError(422, "date_out_of_range", f"date must be between {earliest} and {today}.")

    streak = conn.execute(load_sql("api/streak.sql"), {"today": today}).one()
    profile = conn.execute(load_sql("api/profile.sql")).one()

    # Streak card: always the current week.
    current_week = week_of(today)
    current_nutrition = nutrition_by_day(conn, current_week[0], current_week[-1])
    primary_types = {
        row.day: row.app_type
        for row in conn.execute(
            load_sql("api/primary_activity_types.sql"),
            {"start": current_week[0], "end": current_week[-1]},
        )
    }
    week = []
    for index, day in enumerate(current_week):
        if day > today:
            state, kind = "future", None
        elif day in status_by_day:
            state, kind = status_by_day[day].state, status_by_day[day].kind
        else:
            state, kind = "broken", "miss"  # before the first day with any data
        week.append(
            StreakDay(
                date=day,
                weekday=WEEKDAY_LETTERS[index],
                state=state,
                kind=kind,
                primary_activity_type=primary_types.get(day),
                calorie_status=current_nutrition[day].calorie_status,
            )
        )

    # Everything below follows the selected day.
    recovery_state = conn.execute(
        load_sql("api/recovery_state.sql"), {"today": today, "day": selected}
    ).scalar_one()
    exercises = [
        Exercise(
            id=row.id,
            type=row.type,
            title=row.title,
            started_at=row.started_at.astimezone(ZoneInfo(row.tz or "Asia/Manila")),
            duration_s=row.duration_s,
        )
        for row in conn.execute(
            load_sql("api/activities_on_day.sql"),
            {"date_key": selected.year * 10000 + selected.month * 100 + selected.day},
        )
    ]
    selected_week = week_of(selected)
    selected_nutrition = nutrition_by_day(conn, selected_week[0], selected_week[-1])
    bars = []
    for day in selected_week:
        row = selected_nutrition[day]
        status = "future" if day > today else row.calorie_status
        # No bar for future days or days without calories (UI_SPEC.md 5.8).
        kcal = round(row.kcal) if status not in ("future", "not_logged") else None
        bars.append(WeekBar(date=day, kcal=kcal, budget=row.calorie_budget, status=status))

    return Dashboard(
        today=today,
        selected_date=selected,
        earliest_date=earliest,
        greeting=greeting(now_local),
        nickname=profile.nickname,
        streak=Streak(
            count=streak.streak,
            at_risk=streak.at_risk,
            message=streak_message(streak, best_streak(days)),
            week=week,
        ),
        recovery=Recovery(state=recovery_state),
        exercises=exercises,
        calories=calories_card(selected_nutrition[selected]),
        protein=protein_card(selected_nutrition[selected]),
        week_chart=WeekChart(week_start=selected_week[0], bars=bars),
    )
