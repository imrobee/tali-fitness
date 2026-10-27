import { describe, expect, it } from "vitest";
import { calorieLabel, proteinLabel, streakDayLabel, streakSummary } from "./a11y";
import { addDays, dayOfMonth, isIsoDate } from "./dates";
import { dayLabel, formatDuration, formatNumber, greetingLine } from "./format";
import { arc, proteinFill, ringContent } from "./ring";

describe("dates", () => {
  it("adds days across months and years", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2027-01-01", -1)).toBe("2026-12-31");
  });

  it("accepts only real calendar dates", () => {
    expect(isIsoDate("2026-10-17")).toBe(true);
    expect(isIsoDate("2026-02-30")).toBe(false);
    expect(isIsoDate("17/10/2026")).toBe(false);
    expect(isIsoDate(null)).toBe(false);
  });

  it("reads the day of the month", () => {
    expect(dayOfMonth("2026-10-07")).toBe(7);
  });
});

describe("format", () => {
  it("groups thousands", () => {
    expect(formatNumber(1853)).toBe("1,853");
    expect(formatNumber(653.6)).toBe("654");
  });

  it.each([
    [1920, "32 min"],
    [3600, "1 h"],
    [3900, "1 h 05 min"],
    [4069, "1 h 08 min"],
    [20, "0 min"],
  ])("formats %i seconds as %s", (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected);
  });

  it("names days relative to today", () => {
    expect(dayLabel("2026-10-17", "2026-10-17")).toBe("Today");
    expect(dayLabel("2026-10-16", "2026-10-17")).toBe("Yesterday");
    expect(dayLabel("2026-10-13", "2026-10-17")).toBe("Tue, Oct 13");
  });

  it("drops the comma when there is no nickname", () => {
    expect(greetingLine("Good afternoon", "Rob")).toBe("Good afternoon, Rob");
    expect(greetingLine("Good afternoon", null)).toBe("Good afternoon");
  });
});

describe("ring", () => {
  it("fills by eaten over budget and shows what is left", () => {
    expect(ringContent(654, 1853, "within")).toEqual({
      fill: 654 / 1853,
      tone: "within",
      figure: 1199,
      caption: "kcal left",
    });
  });

  it("is full and orange over budget, saying how much over", () => {
    expect(ringContent(2173, 1853, "over")).toEqual({
      fill: 1,
      tone: "over",
      figure: 320,
      caption: "kcal over",
    });
  });

  it("is empty with no budget or nothing eaten", () => {
    expect(ringContent(654, null, "not_set")).toMatchObject({ fill: 0, figure: null, tone: "empty" });
    expect(ringContent(0, 1853, "not_logged")).toMatchObject({ fill: 0, figure: 1853 });
  });

  it("draws a fraction of the circumference", () => {
    const quarter = arc(10, 0.25);
    expect(quarter.circumference).toBeCloseTo(62.832, 3);
    expect(quarter.dashArray).toBe(`${quarter.circumference / 4} ${quarter.circumference}`);
    expect(arc(10, 2).dashArray.split(" ")[0]).toBe(String(quarter.circumference));
  });

  it("caps the protein bar at 100% but never invents a goal", () => {
    expect(proteinFill(21, 130)).toBeCloseTo(0.1615, 3);
    expect(proteinFill(200, 130)).toBe(1);
    expect(proteinFill(21, null)).toBe(0);
  });
});

describe("accessible names", () => {
  it("reads a streak circle and its marker as one sentence", () => {
    expect(
      streakDayLabel({
        date: "2026-10-13",
        state: "counted",
        kind: "over",
        calorie_status: "over",
      }),
    ).toBe("Tuesday, October 13: over budget, streak kept. Calories: over budget.");
    expect(
      streakDayLabel({
        date: "2026-10-18",
        state: "future",
        kind: null,
        calorie_status: "not_logged",
      }),
    ).toBe("Sunday, October 18: upcoming.");
  });

  it("summarises the streak", () => {
    expect(streakSummary(12, "counted", false)).toBe("Streak: 12 days. Today: counted.");
    expect(streakSummary(1, "pending", true)).toBe(
      "Streak: 1 day. Today: not counted yet. Yesterday can still be filled in.",
    );
  });

  it("reads the ring and the protein bar", () => {
    expect(calorieLabel(654, 1853, "within")).toBe("Calories: 654 eaten of 1,853, 1,199 left.");
    expect(calorieLabel(2173, 1853, "over")).toBe("Calories: 2,173 eaten of 1,853, 320 over budget.");
    expect(proteinLabel(21, 130, 16)).toBe("Protein: 21 of 130 grams, 16 percent.");
  });
});
