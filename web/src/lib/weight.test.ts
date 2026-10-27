import { describe, expect, it } from "vitest";
import type { Weight, WeightDay } from "../api/types";
import { changeLine, chartDomain, goalLine, weightDayLabel, weightHeadline, xFor, yFor } from "./weight";

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
  it("gives the latest weigh-in with its 7-day average", () => {
    expect(weightHeadline(weight())).toBe("Latest 74.8 kg on Tue, Oct 20, 7-day average 74.9 kg.");
  });

  it("says so when nothing has been weighed in the range", () => {
    expect(weightHeadline(weight({ latest_date: null, latest_kg: null, avg_7d_kg: null }))).toBe(
      "No weigh-ins in these days yet.",
    );
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

    expect(weightHeadline(lb, "lb")).toBe("Latest 165.0 lb on Tue, Oct 20, 7-day average 165.0 lb.");
    expect(changeLine(-0.45359237, "lb")).toBe("Down 1.0 lb on last week.");
    expect(goalLine(lb, "lb")).toBe("5.0 lb above your goal of 159.8 lb.");
  });
});
