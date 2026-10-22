import { describe, expect, it } from "vitest";
import type { NutritionPeriod, TrainingPeriod } from "../api/types";
import {
  changeWords,
  lastComplete,
  nutritionBarLabel,
  nutritionHeadline,
  periodAxis,
  rollingLine,
  trainingBarLabel,
  trainingDetail,
  trainingHeadline,
  trainingSoFar,
  trendMax,
} from "./trends";

function training(overrides: Partial<TrainingPeriod> = {}): TrainingPeriod {
  return {
    start: "2026-10-12",
    end: "2026-10-18",
    current: false,
    sessions: 4,
    active_s: 11400,
    run_m: 0,
    volume_kg: 0,
    prev_sessions: 3,
    prev_active_s: 9500,
    active_change_pct: 20,
    ...overrides,
  };
}

function nutrition(overrides: Partial<NutritionPeriod> = {}): NutritionPeriod {
  return {
    start: "2026-10-12",
    end: "2026-10-18",
    current: false,
    days_logged: 5,
    avg_kcal: 1850,
    avg_protein_g: 110,
    avg_budget: 1853,
    days_within: 4,
    days_over: 1,
    status: "within",
    prev_avg_kcal: 1900,
    ...overrides,
  };
}

const THIS_WEEK = { start: "2026-10-19", end: "2026-10-25", current: true };

describe("axis and scale", () => {
  it("labels a week by its Monday and a month by its year", () => {
    expect(periodAxis("week", "2026-10-12")).toEqual(["Oct", "12"]);
    expect(periodAxis("month", "2026-10-01")).toEqual(["Oct", "’26"]);
  });

  it("leaves room above the tallest bar and the budget line, never 0", () => {
    expect(trendMax([1000, 2000, null])).toBeCloseTo(2300);
    expect(trendMax([1500], 1853)).toBeCloseTo(2316.25);
    expect(trendMax([null, 0])).toBe(1);
  });
});

describe("changeWords", () => {
  it("says up, down, or the same, and nothing without a comparison", () => {
    expect(changeWords(20)).toBe("up 20% on");
    expect(changeWords(-25)).toBe("down 25% on");
    expect(changeWords(0)).toBe("the same as");
    expect(changeWords(null)).toBeNull();
  });
});

describe("training", () => {
  it("compares the last finished week, not the one still running", () => {
    const periods = [training(), training({ ...THIS_WEEK, sessions: 1, active_s: 1800 })];

    expect(lastComplete(periods)?.start).toBe("2026-10-12");
    expect(trainingHeadline(periods, "week")).toBe(
      "Last week: 4 sessions, 3 h 10 min, up 20% on the week before.",
    );
    expect(trainingSoFar(periods, "week")).toBe("This week so far: 1 session, 30 min.");
  });

  it("leaves out the change when there is nothing to compare with", () => {
    expect(trainingHeadline([training({ active_change_pct: null })], "month")).toBe(
      "Last month: 4 sessions, 3 h 10 min.",
    );
  });

  it("says so quietly when a period had no training", () => {
    expect(trainingHeadline([training({ sessions: 0, active_s: 0 })], "week")).toBe(
      "No training last week.",
    );
    expect(trainingSoFar([training({ ...THIS_WEEK, sessions: 0, active_s: 0 })], "week")).toBe(
      "This week so far: no training yet.",
    );
  });

  it("lists running distance and lifting volume, leaving out zeros", () => {
    expect(trainingDetail(training({ run_m: 12500, volume_kg: 3490.9 }))).toBe(
      "Running 12.5 km · Lifting 3,491 kg",
    );
    expect(trainingDetail(training({ run_m: 5000 }))).toBe("Running 5 km");
    expect(trainingDetail(training())).toBe("");
  });

  it("speaks each bar, with 'so far' for the running period", () => {
    expect(trainingBarLabel(training(), "week")).toBe("Week of October 12: 4 sessions, 3 h 10 min.");
    expect(trainingBarLabel(training({ ...THIS_WEEK, sessions: 0, active_s: 0 }), "week")).toBe(
      "Week of October 19 so far: no training.",
    );
  });
});

describe("nutrition", () => {
  it("states the 7-day average with protein and the days it covers", () => {
    expect(
      rollingLine({ end_date: "2026-10-19", kcal_avg: 1742, protein_avg_g: 112, days_logged: 6 }),
    ).toBe("7-day average: 1,742 kcal and 112 g protein a day, over 6 logged days.");
    expect(
      rollingLine({ end_date: "2026-10-19", kcal_avg: 1500, protein_avg_g: null, days_logged: 1 }),
    ).toBe("7-day average: 1,500 kcal a day, over 1 logged day.");
    expect(
      rollingLine({ end_date: "2026-10-19", kcal_avg: null, protein_avg_g: null, days_logged: 0 }),
    ).toBe("Nothing logged in the last 7 days.");
  });

  it("sums up the last finished week", () => {
    expect(nutritionHeadline([nutrition(), nutrition(THIS_WEEK)], "week")).toBe(
      "Last week: 1,850 kcal a day, 4 of 5 logged days within budget.",
    );
    expect(nutritionHeadline([nutrition({ status: "not_set" })], "week")).toBe(
      "Last week: 1,850 kcal a day, no budget set.",
    );
    expect(nutritionHeadline([nutrition({ avg_kcal: null, days_logged: 0 })], "month")).toBe(
      "Nothing logged last month.",
    );
  });

  it("speaks each bar with its status", () => {
    expect(nutritionBarLabel(nutrition({ status: "over", avg_kcal: 2100 }), "week")).toBe(
      "Week of October 12: 2,100 kcal a day, over budget on average.",
    );
    expect(
      nutritionBarLabel(nutrition({ ...THIS_WEEK, avg_kcal: null, status: "not_logged" }), "week"),
    ).toBe("Week of October 19 so far: nothing logged.");
  });
});
