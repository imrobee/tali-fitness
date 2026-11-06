import { describe, expect, it } from "vitest";
import type { Weight, WeightDay } from "../api/types";
import {
  averageVertices,
  labelledDots,
  changeLine,
  chartDays,
  chartDomain,
  goalLine,
  pointLabel,
  weightDayLabel,
  weightLines,
  xFor,
  yFor,
} from "./weight";

function weight(overrides: Partial<Weight> = {}): Weight {
  return {
    from: "2026-07-23",
    to: "2026-10-20",
    latest_date: "2026-10-20",
    latest_kg: 74.84,
    avg_7d_kg: 74.9,
    change_7d_kg: -0.3,
    goal_kg: 72.5,
    to_goal_kg: 2.4,
    days: [],
    ...overrides,
  };
}

describe("weight words", () => {
  it("gives the last weigh-in and the 7-day average on separate lines", () => {
    expect(weightLines(weight())).toEqual(["Last weigh-in: 74.8 kg", "7-day average: 74.9 kg"]);
    expect(weightLines(weight({ avg_7d_kg: null }))).toEqual(["Last weigh-in: 74.8 kg"]);
  });

  it("says so when nothing has been weighed in the range", () => {
    expect(weightLines(weight({ latest_date: null, latest_kg: null, avg_7d_kg: null }))).toEqual([
      "No weigh-ins in these days yet.",
    ]);
  });

  it("states the change against last week, rounded to a tenth", () => {
    expect(changeLine(-0.3)).toBe("Down 0.3 kg on last week.");
    expect(changeLine(0.04)).toBe("No change on last week.");
    expect(changeLine(1.26)).toBe("Up 1.3 kg on last week.");
    expect(changeLine(null)).toBeNull();
  });

  it("measures the distance to the goal from the average", () => {
    expect(goalLine(weight())).toBe("2.4 kg above your goal of 72.5 kg.");
    expect(goalLine(weight({ to_goal_kg: -0.8 }))).toBe("At or below your goal of 72.5 kg.");
    expect(goalLine(weight({ goal_kg: null, to_goal_kg: null }))).toBe(
      "Set a weight goal on Me to see how far you are from it.",
    );
  });

  it("labels a day with its weight or with no weigh-in", () => {
    const logged: WeightDay = {
      date: "2026-10-20", weight_kg: 74.84, avg_7d_kg: 74.9, change_7d_kg: null, goal_kg: null,
      status: "not_set",
    };
    expect(weightDayLabel(logged)).toBe("Tuesday, October 20: 74.8 kg.");
    expect(weightDayLabel({ ...logged, weight_kg: null, status: "not_logged" })).toBe(
      "Tuesday, October 20: no weigh-in.",
    );
  });
});

describe("chart placement", () => {
  it("keeps the goal and every point inside half a kilogram of the frame", () => {
    expect(chartDomain([74.8, 75.2, null], 72.5)).toEqual({ min: 71.5, max: 76.5 });
  });

  it("gives a flat week a little room, and an empty chart a default range", () => {
    expect(chartDomain([75, 75, null], null)).toEqual({ min: 74.5, max: 75.5 });
    expect(chartDomain([null], null)).toEqual({ min: 70, max: 80 });
  });

  it("puts heavier weight higher up and the first day at the left edge", () => {
    const domain = { min: 70, max: 80 };

    expect(yFor(80, domain, 100)).toBe(0);
    expect(yFor(70, domain, 100)).toBe(100);
    expect(xFor(0, 8, 300)).toBe(0);
    expect(xFor(7, 8, 300)).toBe(300);
  });
});

describe("weight in pounds", () => {
  it("shows the same weigh-in, change and goal in lb", () => {
    const lb = weight({ latest_kg: 74.84274105, avg_7d_kg: 74.84274105, to_goal_kg: 2.26796185 });

    expect(weightLines(lb, "lb")).toEqual(["Last weigh-in: 165.0 lb", "7-day average: 165.0 lb"]);
    expect(pointLabel(74.84274105, "lb")).toBe("165");
    expect(pointLabel(74.84, "kg")).toBe("74.8");
    expect(changeLine(-0.45359237, "lb")).toBe("Down 1.0 lb on last week.");
    expect(goalLine(lb, "lb")).toBe("5.0 lb above your goal of 159.8 lb.");
  });
});

describe("average line", () => {
  it("bends only on days with a weigh-in, never between them", () => {
    const days = [
      { weight_kg: 75.1, avg_7d_kg: 75.1 },
      { weight_kg: null, avg_7d_kg: 75.0 }, // the average moved, but nothing was weighed
      { weight_kg: 74.6, avg_7d_kg: 74.85 },
      { weight_kg: 74.9, avg_7d_kg: null },
    ];

    expect(averageVertices(days)).toEqual([
      { index: 0, avgKg: 75.1 },
      { index: 2, avgKg: 74.85 },
    ]);
  });
});

describe("point labels", () => {
  it("label the latest weigh-in, then only dots far enough apart not to overlap", () => {
    expect([...labelledDots([0, 10, 20, 30, 40, 50], 25)].sort((a, b) => a - b)).toEqual([2, 5]);
    expect([...labelledDots([0, 100, 200], 25)].sort((a, b) => a - b)).toEqual([0, 1, 2]);
    expect(labelledDots([], 25).size).toBe(0);
  });
});

describe("chart days", () => {
  const empty = { avg_7d_kg: null, change_7d_kg: null, goal_kg: null, status: "not_logged" as const };

  it("starts at the first weigh-in, so the first point is at the left edge", () => {
    const days = [
      { date: "2026-10-18", weight_kg: null, ...empty },
      { date: "2026-10-19", weight_kg: 75.1, ...empty },
      { date: "2026-10-20", weight_kg: null, ...empty },
    ];

    expect(chartDays(days).map((d) => d.date)).toEqual(["2026-10-19", "2026-10-20"]);
    expect(xFor(0, chartDays(days).length, 300)).toBe(0);
  });

  it("draws a single weigh-in at the left edge, and nothing without one", () => {
    expect(xFor(0, 1, 300)).toBe(0);
    expect(chartDays([{ date: "2026-10-20", weight_kg: null, ...empty }])).toEqual([]);
  });
});
