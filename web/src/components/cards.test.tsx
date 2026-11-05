// @vitest-environment jsdom
// Card states from API payloads (ARCHITECTURE.md 13: "card states from payloads").

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  ActivitySummary,
  Calendar,
  Dashboard,
  NutritionTrend,
  PipelineHealth,
  RecoveryState,
  StreakDay,
  TrainingPeriod,
  Weight,
  WeekBar,
} from "../api/types";
import { CalendarCard } from "./CalendarCard";
import { CalorieCard } from "./CalorieCard";
import { DataSyncCard } from "./DataSyncCard";
import { DayChooser } from "./DayChooser";
import { ActivityItem } from "./ActivityItem";
import { ExercisesCard } from "./ExercisesCard";
import { ProteinCard } from "./ProteinCard";
import { RecoveryCard } from "./RecoveryCard";
import { StreakCard } from "./StreakCard";
import { RecordsCard } from "./ProgressCards";
import { NutritionTrendCard, TrainingTrendCard } from "./TrendCards";
import { WeightCard } from "./WeightCard";
import { WeeklyCard } from "./WeeklyCard";

afterEach(() => {
  cleanup();
  localStorage.clear();
});

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const TODAY = "2026-10-17"; // a Saturday

function day(date: string, weekday: string, state: StreakDay["state"], extra: Partial<StreakDay> = {}) {
  return {
    date,
    weekday,
    state,
    kind: state === "future" ? null : "success",
    recovery_logged: false,
    primary_activity_type: state === "counted" ? "run" : null,
    calorie_status: state === "future" ? "not_logged" : "within",
    ...extra,
  } as StreakDay;
}

const WEEK: StreakDay[] = [
  day("2026-10-12", "M", "counted"),
  day("2026-10-13", "T", "counted", { kind: "over", primary_activity_type: "strength", calorie_status: "over" }),
  day("2026-10-14", "W", "counted", { kind: "recovery", calorie_status: "within" }),
  day("2026-10-15", "T", "counted"),
  day("2026-10-16", "F", "at_risk", { kind: "miss", calorie_status: "not_logged" }),
  day("2026-10-17", "S", "pending", { kind: "miss", calorie_status: "not_logged" }),
  day("2026-10-18", "S", "future"),
];

describe("StreakCard", () => {
  const streak = { count: 6, at_risk: true, message: "Yesterday isn't logged. Fill it in to keep your 6-day streak.", week: WEEK };

  it("reads each circle and its marker as one sentence", () => {
    wrap(<StreakCard streak={streak} today={TODAY} />);

    expect(screen.getByText("Tuesday, October 13: over budget, streak kept. Calories: over budget.")).toBeTruthy();
    expect(screen.getByText("Streak: 6 days. Today: not counted yet. Yesterday can still be filled in.")).toBeTruthy();
  });

  it("draws the calorie ring: grey, green, or orange with a gap and a triangle", () => {
    const { container } = wrap(<StreakCard streak={streak} today={TODAY} />);

    const rings = [...container.querySelectorAll("svg circle")];
    expect(rings).toHaveLength(6); // no ring on the future Sunday
    const over = rings[1];
    expect(over.getAttribute("stroke-dasharray")).not.toBeNull();
    expect(rings[0].getAttribute("stroke-dasharray")).toBeNull(); // a full ring when within
    expect(container.querySelectorAll("svg polygon")).toHaveLength(1); // only the over day
    expect(container.querySelectorAll("svg text")).toHaveLength(0); // no "!" any more
  });

  it("shows a past rest day without a workout as the snowflake, and today as its date", () => {
    const week = WEEK.map((d) => (d.date === TODAY ? { ...d, kind: "recovery" as const } : d));
    const { container } = wrap(<StreakCard streak={{ ...streak, week }} today={TODAY} />);

    // The visible circles only; each day's spoken label is in a hidden span beside them.
    const circles = [...container.querySelectorAll("ol li > [aria-hidden] > span")];
    expect(circles[2].textContent).toBe(""); // Wednesday: the snowflake
    expect(circles[5].textContent).toBe("17"); // today: still open, not a rest day yet
  });

  it("is for reading only: no buttons or links to pick a day, only the ? that explains it", () => {
    wrap(<StreakCard streak={streak} today={TODAY} />);

    expect(screen.queryAllByRole("button").map((button) => button.getAttribute("aria-label"))).toEqual([
      "How streaks work",
    ]);
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });
});

describe("RecoveryCard", () => {
  const cases: [RecoveryState, string, string | null][] = [
    ["available", "Taking a recovery day?", "Log recovery"],
    ["logged", "Recovery day logged", "Undo"],
    ["blocked", "Rest day yesterday", null],
    ["counted", "This day counted", null],
    ["locked", "Recovery day", null],
  ];

  it.each(cases)("shows the %s state", (state, title, button) => {
    wrap(<RecoveryCard recovery={{ state }} selectedDate={TODAY} />);

    expect(screen.getByRole("heading", { name: title })).toBeTruthy();
    if (button) expect(screen.getByRole("button", { name: button })).toBeTruthy();
    else expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByText(/freeze/i)).toBeNull(); // the single freeze is gone (Slice 7d)
  });
});

describe("ExercisesCard", () => {
  const exercises = [
    { id: 3, type: "strength", title: "Full Body", started_at: "2026-10-17T16:39:00+08:00", duration_s: 4069 },
    { id: 2, type: "run", title: "Afternoon Run", started_at: "2026-10-17T12:00:00+08:00", duration_s: 1920 },
    { id: 1, type: "walk", title: "Morning Walk", started_at: "2026-10-17T07:00:00+08:00", duration_s: 3600 },
  ];

  it("starts with one row and a chevron for the rest", () => {
    wrap(<ExercisesCard exercises={exercises} to="/activities" />);

    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByText("Full Body")).toBeTruthy();
    expect(screen.getByText("1 h 08 min")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Show 2 more exercises" }));

    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Show fewer exercises" }).getAttribute("aria-expanded")).toBe("true");
  });

  it("links the whole card to Activities", () => {
    wrap(<ExercisesCard exercises={exercises} to="/activities?date=2026-10-17" />);

    expect(screen.getByRole("link", { name: "Activities" }).getAttribute("href")).toBe(
      "/activities?date=2026-10-17",
    );
  });

  it("says so when the day has none, with no chevron", () => {
    wrap(<ExercisesCard exercises={[]} />);

    expect(screen.getByText("No exercises logged for this day.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("CalorieCard", () => {
  const card = (calories: Partial<Dashboard["calories"]>) => (
    <CalorieCard
      calories={{ eaten: 0, budget: 1853, remaining: 1853, over: 0, status: "not_logged", ...calories }}
    />
  );

  it("shows what is left within budget", () => {
    wrap(card({ eaten: 654, remaining: 1199, status: "within" }));

    expect(screen.getByRole("img", { name: "Calories: 654 eaten of 1,853, 1,199 left." })).toBeTruthy();
    expect(screen.getByText("1,199")).toBeTruthy();
    expect(screen.getByText("kcal left")).toBeTruthy();
  });

  it("shows the overage in words over budget", () => {
    wrap(card({ eaten: 2173, remaining: 0, over: 320, status: "over" }));

    expect(screen.getByText("320")).toBeTruthy();
    expect(screen.getByText("kcal over")).toBeTruthy();
  });

  it("links to Me when no budget is set", () => {
    wrap(card({ eaten: 654, budget: null, remaining: null, over: null, status: "not_set" }));

    expect(screen.getByRole("link", { name: "Set your calorie budget" }).getAttribute("href")).toBe("/me");
  });
});

describe("ProteinCard", () => {
  it("shows grams, what is left, and the percentage", () => {
    wrap(<ProteinCard protein={{ grams: 21, goal: 130, percent: 16 }} />);

    expect(screen.getByText("21g, 109g left")).toBeTruthy();
    expect(screen.getByText("16%")).toBeTruthy();
  });

  it("asks for a goal when none is set", () => {
    wrap(<ProteinCard protein={{ grams: 21, goal: null, percent: null }} />);

    expect(screen.getByRole("link", { name: "Set a protein goal" })).toBeTruthy();
  });
});

describe("DayChooser", () => {
  it("cannot go past today or before the first day", () => {
    wrap(<DayChooser selected={TODAY} today={TODAY} earliest="2026-07-30" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Next day" })).toHaveProperty("disabled", true);
    cleanup();

    wrap(<DayChooser selected="2026-07-30" today={TODAY} earliest="2026-07-30" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Previous day" })).toHaveProperty("disabled", true);
  });

  it("steps a day at a time", () => {
    const onChange = vi.fn();
    wrap(<DayChooser selected="2026-10-15" today={TODAY} earliest="2026-07-30" onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Previous day" }));
    fireEvent.click(screen.getByRole("button", { name: "Next day" }));

    expect(onChange.mock.calls).toEqual([["2026-10-14"], ["2026-10-16"]]);
  });

  it("picks a day from the date picker in the middle, today as null", () => {
    const onChange = vi.fn();
    wrap(<DayChooser selected="2026-10-15" today={TODAY} earliest="2026-07-30" onChange={onChange} />);
    const picker = screen.getByLabelText("Choose a day. Showing Thu, Oct 15");

    expect(picker.getAttribute("min")).toBe("2026-07-30");
    expect(picker.getAttribute("max")).toBe(TODAY);
    fireEvent.change(picker, { target: { value: "2026-09-01" } });
    fireEvent.change(picker, { target: { value: TODAY } });
    fireEvent.change(picker, { target: { value: "" } }); // a cleared picker changes nothing

    expect(onChange.mock.calls).toEqual([["2026-09-01"], [null]]);
  });
});

describe("Data and sync panel", () => {
  const NOW = Date.parse("2026-10-20T12:00:00Z");
  const health: PipelineHealth = {
    now: "2026-10-20T12:00:00Z",
    sources: [
      { source: "strava", last_success_at: "2026-10-20T03:00:00Z", status: "delayed", failures_7d: 0 },
      { source: "health", last_success_at: null, status: "failed", failures_7d: 2 },
    ],
    quarantine: {
      open: 1,
      by_reason: { unparsed_line: 1 },
      recent: [
        {
          source: "strava",
          entity_id: "42",
          line_no: 3,
          reason_code: "unparsed_line",
          raw_snippet: "Set 1: ???",
          first_seen_at: "2026-10-20T03:00:00Z",
        },
      ],
    },
    dq: {
      passed: 14,
      warnings: 1,
      failed: 0,
      checked_at: "2026-10-20T11:30:00Z",
      checks: [
        {
          check_name: "unmapped_exercises",
          status: "warn",
          observed_value: 1,
          threshold: "exercises with muscle_group Unmapped: warn > 0",
          checked_at: "2026-10-20T11:30:00Z",
        },
      ],
    },
  };

  it("shows each source's status as text, not colour alone", () => {
    wrap(<DataSyncCard health={health} now={NOW} />);

    expect(screen.getByText("Delayed")).toBeTruthy();
    expect(screen.getByText("Failed")).toBeTruthy();
    expect(screen.getByText(/Last successful sync 9 hours ago/)).toBeTruthy();
    expect(screen.getByText("No successful sync yet")).toBeTruthy();
    expect(screen.getByText("2 failures in the last 7 days")).toBeTruthy();
  });

  it("opens the quarantine and data-quality lists on demand", () => {
    wrap(<DataSyncCard health={health} now={NOW} />);

    const quarantine = screen.getByRole("button", { name: /Quarantined records: 1/ });
    expect(quarantine.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("Set 1: ???")).toBeNull();

    fireEvent.click(quarantine);
    expect(quarantine.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("Set 1: ???")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Data quality: 14 passed/ }));
    expect(screen.getByText("unmapped exercises")).toBeTruthy();
  });

  it("says so when nothing is waiting in quarantine", () => {
    wrap(
      <DataSyncCard
        health={{ ...health, quarantine: { open: 0, by_reason: {}, recent: [] } }}
        now={NOW}
      />,
    );

    expect(screen.getByText(/Quarantined records: 0\. Nothing waiting for a fix\./)).toBeTruthy();
  });
});

describe("Activities rows", () => {
  const run: ActivitySummary = {
    id: 1,
    type: "run",
    title: "Morning Run",
    started_at: "2026-10-20T00:10:00Z",
    duration_s: 1740,
    moving_s: 1700,
    distance_m: 5230,
    parse_status: "not_applicable",
    exercise_count: 0,
    set_count: 0,
    volume_kg: 0,
  };
  const lifting: ActivitySummary = {
    ...run,
    id: 2,
    type: "strength",
    title: "Full Body",
    distance_m: null,
    parse_status: "ok",
    exercise_count: 9,
    set_count: 22,
    volume_kg: 3490.9,
  };

  it("shows a run as a plain row with its pace, not as a button", () => {
    wrap(
      <ul>
        <ActivityItem activity={run} />
      </ul>,
    );

    expect(screen.getByText("Morning Run")).toBeTruthy();
    expect(screen.getByText("5.2 km · 5:25 /km · 29 min")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("opens lifting sessions from a closed button with the volume in the summary", () => {
    wrap(
      <ul>
        <ActivityItem activity={lifting} />
      </ul>,
    );

    const toggle = screen.getByRole("button", { name: /Full Body/ });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByText("9 exercises · 22 sets · 3,491 kg")).toBeTruthy();
  });
});

describe("Calories by day card", () => {
  // Monday 12 October to Sunday 18 October. Saturday 17 is today; Sunday 18 is in the future.
  const bars: WeekBar[] = [
    { date: "2026-10-12", kcal: 1700, budget: 1853, status: "within" },
    { date: "2026-10-13", kcal: 2173, budget: 1853, status: "over" },
    { date: "2026-10-14", kcal: 1200, budget: null, status: "not_set" },
    { date: "2026-10-15", kcal: null, budget: 1853, status: "not_logged" },
    { date: "2026-10-16", kcal: 1650, budget: 1853, status: "within" },
    { date: "2026-10-17", kcal: 654, budget: 1853, status: "within" },
    { date: "2026-10-18", kcal: null, budget: 1853, status: "future" },
  ];

  it("names each day with its calories and status, and the week in one sentence", () => {
    wrap(<WeeklyCard bars={bars} today="2026-10-17" selected="2026-10-17" onSelect={() => {}} />);

    expect(screen.getByRole("button", { name: /2,173 kcal, over budget/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /not logged/ })).toBeTruthy();
    expect(screen.getByText("Weekly calories: 3 days within budget, 1 over, budget 1,853.")).toBeTruthy();
  });

  it("names the week it shows: This week, or its dates", () => {
    wrap(<WeeklyCard bars={bars} today="2026-10-17" selected="2026-10-17" onSelect={() => {}} />);
    expect(screen.getByText("This week")).toBeTruthy();
    cleanup();

    wrap(<WeeklyCard bars={bars} today="2026-10-27" selected="2026-10-17" onSelect={() => {}} />);
    expect(screen.getByText("Oct 12 – 18")).toBeTruthy();
  });

  it("marks the selected day and cannot select a future day", () => {
    const onSelect = vi.fn();
    wrap(<WeeklyCard bars={bars} today="2026-10-17" selected="2026-10-17" onSelect={onSelect} />);

    const today = screen.getByRole("button", { name: /Saturday, October 17/ });
    expect(today.getAttribute("aria-current")).toBe("date");

    const future = screen.getByRole("button", { name: /Sunday, October 18/ }) as HTMLButtonElement;
    expect(future.disabled).toBe(true);
  });

  it("selects the day that was tapped", () => {
    const onSelect = vi.fn();
    wrap(<WeeklyCard bars={bars} today="2026-10-17" selected="2026-10-17" onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: /Monday, October 12/ }));

    expect(onSelect).toHaveBeenCalledWith("2026-10-12");
  });
});

describe("Activities calendar", () => {
  // The week of Monday 12 October; Saturday 17 is today.
  const calendar: Calendar = {
    view: "week",
    today: "2026-10-17",
    period_start: "2026-10-12",
    period_end: "2026-10-18",
    previous: "2026-10-05",
    next: null,
    days: [12, 13, 14, 15, 16, 17, 18].map((d) => ({
      date: `2026-10-${d}`,
      in_period: true,
      future: d === 18,
      activity_count: d === 14 ? 2 : d === 12 ? 1 : 0,
      primary_activity_type: d === 14 ? "strength" : d === 12 ? "run" : null,
      recovery: d === 15,
    })),
  };

  function renderCalendar(selected: string | null = null) {
    const handlers = { onSelect: vi.fn(), onMove: vi.fn(), onViewChange: vi.fn() };
    wrap(<CalendarCard calendar={calendar} view="week" selected={selected} {...handlers} />);
    return handlers;
  }

  it("names each day with its activities and cannot pick a future day", () => {
    renderCalendar();

    expect(
      screen.getByRole("button", { name: "Wednesday, October 14: 2 activities, the longest a strength session." }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Thursday, October 15: recovery day." })).toBeTruthy();
    const future = screen.getByRole("button", { name: /Sunday, October 18/ }) as HTMLButtonElement;
    expect(future.disabled).toBe(true);
    expect(screen.getByText("Oct 12 – 18")).toBeTruthy();
  });

  it("filters to the tapped day, and tapping it again shows all days", () => {
    const first = renderCalendar();
    fireEvent.click(screen.getByRole("button", { name: /Monday, October 12/ }));
    expect(first.onSelect).toHaveBeenCalledWith("2026-10-12");

    cleanup();
    const second = renderCalendar("2026-10-12");
    const monday = screen.getByRole("button", { name: /Monday, October 12/ });
    expect(monday.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(monday);
    expect(second.onSelect).toHaveBeenCalledWith(null);
  });

  it("moves with the server's previous date and stops where it has none", () => {
    const { onMove } = renderCalendar();

    fireEvent.click(screen.getByRole("button", { name: "Previous week" }));
    expect(onMove).toHaveBeenCalledWith("2026-10-05");
    expect((screen.getByRole("button", { name: "Next week" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("switches between week and month", () => {
    const { onViewChange } = renderCalendar();

    expect(screen.getByRole("button", { name: "Week" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Month" }));
    expect(onViewChange).toHaveBeenCalledWith("month");
  });
});

describe("Trend cards", () => {
  const trainingPeriods: TrainingPeriod[] = [
    {
      start: "2026-10-12", end: "2026-10-18", current: false, sessions: 4, active_s: 11400,
      run_m: 12500, volume_kg: 3490.9, prev_sessions: 3, prev_active_s: 9500, active_change_pct: 20,
    },
    {
      start: "2026-10-19", end: "2026-10-25", current: true, sessions: 1, active_s: 1800,
      run_m: 5000, volume_kg: 0, prev_sessions: 4, prev_active_s: 11400, active_change_pct: -84,
    },
  ];

  it("leads training with the last finished week and speaks every bar", () => {
    wrap(
      <TrainingTrendCard trend={{ grain: "week", periods: trainingPeriods }} grain="week" onGrainChange={() => {}} />,
    );

    expect(screen.getByText("Last week: 4 sessions, 3 h 10 min, up 20% on the week before.")).toBeTruthy();
    expect(screen.getByText("Running 12.5 km · Lifting 3,491 kg")).toBeTruthy();
    expect(screen.getByText("Week of October 19 so far: 1 session, 30 min.")).toBeTruthy();
  });

  it("leads nutrition with the 7-day average and draws the budget line's value", () => {
    const trend: NutritionTrend = {
      grain: "week",
      rolling_7d: { end_date: "2026-10-18", kcal_avg: 1742, protein_avg_g: 112, days_logged: 6 },
      periods: [
        {
          start: "2026-10-12", end: "2026-10-18", current: false, days_logged: 5, avg_kcal: 1850,
          avg_protein_g: 110, avg_budget: 1853, days_within: 4, days_over: 1, status: "within",
          prev_avg_kcal: null,
        },
      ],
    };
    wrap(<NutritionTrendCard trend={trend} grain="week" onGrainChange={() => {}} />);

    expect(screen.getByText("7-day average: 1,742 kcal and 112 g of protein a day")).toBeTruthy();
    expect(screen.queryByText(/^Last week: /)).toBeNull();
    expect(screen.queryByText("Averages count logged days only.")).toBeNull();
    expect(screen.getByText("Week of October 12: 1,850 kcal a day, within budget on average.")).toBeTruthy();
    expect(screen.getByText("1,853")).toBeTruthy();
  });
});

describe("Weight card", () => {
  const weight: Weight = {
    from: "2026-07-23",
    to: "2026-10-20",
    latest_date: "2026-10-20",
    latest_kg: 74.84,
    avg_7d_kg: 74.9,
    change_7d_kg: -0.3,
    goal_kg: 72.5,
    to_goal_kg: 2.4,
    days: [
      { date: "2026-10-19", weight_kg: 75.1, avg_7d_kg: 75.0, change_7d_kg: null, goal_kg: 72.5, status: "above" },
      { date: "2026-10-20", weight_kg: null, avg_7d_kg: 74.9, change_7d_kg: -0.3, goal_kg: 72.5, status: "not_logged" },
    ],
  };

  it("says the latest weight, the change and the distance to goal in words", () => {
    wrap(<WeightCard weight={weight} />);

    expect(screen.getByText("Last weigh-in: 74.8 kg")).toBeTruthy();
    expect(screen.getByText("7-day average: 74.9 kg")).toBeTruthy();
    // Each weigh-in's dot carries its weight; a day without one gets no label.
    expect(screen.getByText("75.1")).toBeTruthy();
    expect(screen.getByText("Down 0.3 kg on last week.")).toBeTruthy();
    expect(screen.getByText("2.4 kg above your goal of 72.5 kg.")).toBeTruthy();
  });

  it("gives each weigh-in a spoken label and skips days with none", () => {
    wrap(<WeightCard weight={weight} />);

    expect(screen.getByText("Monday, October 19: 75.1 kg.")).toBeTruthy();
    expect(screen.queryByText(/no weigh-in/)).toBeNull();
  });
});

describe("Progress cards", () => {
  const records = Array.from({ length: 7 }, (_, i) => ({
    exercise: `Lift ${i + 1}`, equipment: null, muscle_group: "Chest", e1rm_kg: 50 + i, weight_kg: 40,
    reps: 8, date: "2026-10-13", activity_id: i, prev_e1rm_kg: null, sessions: 1, recent: i === 0,
  }));

  it("shows five records, then the rest on demand", () => {
    wrap(<RecordsCard records={records} unit="kg" />);

    expect(screen.getAllByRole("listitem")).toHaveLength(5);
    fireEvent.click(screen.getByRole("button", { name: /Show 2 more/ }));
    expect(screen.getAllByRole("listitem")).toHaveLength(7);
    expect(screen.getByRole("listitem", { name: /^Lift 1: / })).toBeTruthy();
  });

  it("shows no count, no New badge, no gain and no formula line", () => {
    wrap(<RecordsCard records={[{ ...records[0], prev_e1rm_kg: 45 }]} unit="kg" />);

    expect(screen.queryByText("New")).toBeNull();
    expect(screen.queryByText(/on the record before/)).toBeNull();
    expect(screen.queryByText(/Estimated one-rep max/)).toBeNull();
    expect(screen.queryByText("1")).toBeNull();
  });
});
