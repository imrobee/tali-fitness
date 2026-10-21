// @vitest-environment jsdom
// Card states from API payloads (ARCHITECTURE.md 13: "card states from payloads").

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  ActivitySummary,
  Dashboard,
  PipelineHealth,
  RecoveryState,
  StreakDay,
  WeekBar,
} from "../api/types";
import { CalorieCard } from "./CalorieCard";
import { DataSyncCard } from "./DataSyncCard";
import { DayChooser } from "./DayChooser";
import { ActivityItem } from "./ActivityItem";
import { ExercisesCard } from "./ExercisesCard";
import { KeyGate } from "./KeyGate";
import { ProteinCard } from "./ProteinCard";
import { RecoveryCard } from "./RecoveryCard";
import { StreakCard } from "./StreakCard";
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
    primary_activity_type: state === "qualifying" ? "run" : null,
    calorie_status: state === "future" ? "not_logged" : "within",
    ...extra,
  } as StreakDay;
}

const WEEK: StreakDay[] = [
  day("2026-10-12", "M", "qualifying"),
  day("2026-10-13", "T", "qualifying", { primary_activity_type: "strength", calorie_status: "over" }),
  day("2026-10-14", "W", "recovery", { calorie_status: "not_logged" }),
  day("2026-10-15", "T", "qualifying"),
  day("2026-10-16", "F", "at_risk", { calorie_status: "not_logged" }),
  day("2026-10-17", "S", "today_pending"),
  day("2026-10-18", "S", "future"),
];

describe("StreakCard", () => {
  const streak = { count: 6, at_risk: true, message: "Yesterday isn't logged. Fill it in to keep your 6-day streak.", week: WEEK };

  it("reads each circle and its marker as one sentence", () => {
    wrap(<StreakCard streak={streak} today={TODAY} selectedDate={TODAY} onSelect={() => {}} />);

    expect(
      screen.getByRole("button", {
        name: "Tuesday, October 13: qualifying day. Workout. Calories: over budget.",
      }),
    ).toBeTruthy();
    expect(screen.getByText("Streak: 6 days. Today: not counted yet. Yesterday isn't logged yet.")).toBeTruthy();
  });

  it("lets past days and today be selected, but not future days", () => {
    const onSelect = vi.fn();
    wrap(<StreakCard streak={streak} today={TODAY} selectedDate={TODAY} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: /^Monday, October 12/ }));
    expect(onSelect).toHaveBeenCalledWith("2026-10-12");
    expect(screen.getByRole("button", { name: "Sunday, October 18: upcoming." })).toHaveProperty(
      "disabled",
      true,
    );
    expect(screen.getByRole("button", { name: /^Saturday, October 17/ }).getAttribute("aria-pressed")).toBe("true");
  });

  it("offers Fill in for an at-risk yesterday", () => {
    const onSelect = vi.fn();
    wrap(<StreakCard streak={streak} today={TODAY} selectedDate={TODAY} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole("button", { name: "Fill in" }));

    expect(onSelect).toHaveBeenCalledWith("2026-10-16");
  });
});

describe("RecoveryCard", () => {
  const cases: [RecoveryState, string, string | null, string | null][] = [
    ["available", "Taking a recovery day?", "1 freeze available", "Log recovery"],
    ["logged", "Recovery day logged", "Freeze used", "Undo"],
    ["no_freeze", "No freezes left", "0 freezes", null],
    ["blocked", "Fill in yesterday first", "0 freezes", "Go to yesterday"],
    ["counted", "This day counted", "1 freeze available", null],
    ["locked", "Recovery day", null, null],
  ];

  it.each(cases)("shows the %s state", (state, title, pill, button) => {
    const freezes = state === "logged" || state === "no_freeze" || state === "blocked" ? 0 : 1;
    wrap(
      <RecoveryCard
        recovery={{ state, freezes_left: freezes, freezes_max: 1 }}
        selectedDate={TODAY}
        onSelect={() => {}}
      />,
    );

    expect(screen.getByRole("heading", { name: title })).toBeTruthy();
    if (pill) expect(screen.getByText(pill)).toBeTruthy();
    if (button) expect(screen.getByRole("button", { name: button })).toBeTruthy();
    else expect(screen.queryByRole("button")).toBeNull();
  });

  it("goes to yesterday when blocked", () => {
    const onSelect = vi.fn();
    wrap(
      <RecoveryCard
        recovery={{ state: "blocked", freezes_left: 0, freezes_max: 1 }}
        selectedDate={TODAY}
        onSelect={onSelect}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Go to yesterday" }));

    expect(onSelect).toHaveBeenCalledWith("2026-10-16");
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

    expect(screen.getByRole("link", { name: "Logged exercises" }).getAttribute("href")).toBe(
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

  it("steps a day at a time and jumps back to today", () => {
    const onChange = vi.fn();
    wrap(<DayChooser selected="2026-10-15" today={TODAY} earliest="2026-07-30" onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Previous day" }));
    fireEvent.click(screen.getByRole("button", { name: "Thu, Oct 15. Jump to today" }));

    expect(onChange.mock.calls).toEqual([["2026-10-14"], [null]]);
  });
});

describe("KeyGate", () => {
  it("asks for the key, then shows the app", () => {
    wrap(
      <KeyGate>
        <p>The app</p>
      </KeyGate>,
    );

    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "abc123" } });
    fireEvent.click(screen.getByRole("button", { name: "Connect" }));

    expect(screen.getByText("The app")).toBeTruthy();
    expect(localStorage.getItem("fitness-tracker.api-key")).toBe("abc123");
  });

  it("comes back with a message after a 401", async () => {
    localStorage.setItem("fitness-tracker.api-key", "wrong");
    wrap(
      <KeyGate>
        <p>The app</p>
      </KeyGate>,
    );

    window.dispatchEvent(new Event("api:unauthorized"));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText("The app")).toBeNull();
    expect(localStorage.getItem("fitness-tracker.api-key")).toBeNull();
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

describe("Weekly calorie budget card", () => {
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
