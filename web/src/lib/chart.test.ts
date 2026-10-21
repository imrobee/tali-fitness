import { describe, expect, it } from "vitest";
import type { BarStatus, WeekBar } from "../api/types";
import { barLabel, chartMax, chartSummary, hasBar, percentOf, weekdayLetters } from "./chart";

const bar = (date: string, status: BarStatus, kcal: number | null, budget: number | null = 1853): WeekBar => ({
  date,
  kcal,
  budget,
  status,
});

describe("scale", () => {
  it("leaves room above the budget and above the tallest bar", () => {
    // 1.1 x 2173 = 2390.3 beats 1.25 x 1853 = 2316.25, so the tallest bar sets the top.
    expect(chartMax([bar("2026-10-13", "over", 2173)])).toBeCloseTo(2390.3);
    // A quiet week: the budget sets the top.
    expect(chartMax([bar("2026-10-13", "within", 800)])).toBeCloseTo(2316.25);
    // A bar far above the budget sets the top instead.
    expect(chartMax([bar("2026-10-13", "over", 4000)])).toBeCloseTo(4400);
  });

  it("is never zero, so an empty week still has a scale", () => {
    expect(chartMax([bar("2026-10-13", "not_logged", null, null)])).toBe(1);
  });

  it("keeps percentages between 0 and 100", () => {
    expect(percentOf(926.5, 1853)).toBeCloseTo(50);
    expect(percentOf(3000, 1853)).toBe(100);
    expect(percentOf(-5, 1853)).toBe(0);
  });
});

describe("which days get a bar", () => {
  it("skips future and not-logged days", () => {
    expect(hasBar(bar("2026-10-18", "future", null))).toBe(false);
    expect(hasBar(bar("2026-10-12", "not_logged", null))).toBe(false);
    expect(hasBar(bar("2026-10-17", "within", 654))).toBe(true);
    expect(hasBar(bar("2026-10-16", "not_set", 1200, null))).toBe(true);
  });
});

describe("labels", () => {
  it("gives the weekday letters used under the bars", () => {
    expect(weekdayLetters("2026-10-19")).toBe("Mo");
    expect(weekdayLetters("2026-10-25")).toBe("Su");
  });

  it("speaks each day with its calories and status", () => {
    expect(barLabel(bar("2026-10-13", "over", 2173), "Tuesday")).toBe("Tuesday: 2,173 kcal, over budget");
    expect(barLabel(bar("2026-10-12", "not_logged", null), "Monday")).toBe("Monday: not logged");
  });

  it("summarises the week in one sentence", () => {
    const week = [
      bar("2026-10-12", "within", 1700),
      bar("2026-10-13", "over", 2173),
      bar("2026-10-14", "within", 1650),
      bar("2026-10-15", "within", 1500),
      bar("2026-10-16", "within", 1800),
      bar("2026-10-17", "within", 654),
      bar("2026-10-18", "future", null),
    ];

    expect(chartSummary(week)).toBe("Weekly calories: 5 days within budget, 1 over, budget 1,853.");
  });

  it("leaves the budget out of the summary when days have different budgets", () => {
    const week = [bar("2026-10-12", "within", 1700, 1853), bar("2026-10-13", "within", 1500, 1600)];

    expect(chartSummary(week)).toBe("Weekly calories: 2 days within budget.");
  });
});
