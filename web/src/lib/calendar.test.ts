import { describe, expect, it } from "vitest";
import type { CalendarDay } from "../api/types";
import { calendarDayLabel, periodTitle } from "./calendar";

function day(overrides: Partial<CalendarDay> = {}): CalendarDay {
  return {
    date: "2026-10-14",
    in_period: true,
    future: false,
    activity_count: 0,
    primary_activity_type: null,
    recovery: false,
    ...overrides,
  };
}

describe("periodTitle", () => {
  it("names a month with its year", () => {
    expect(periodTitle("month", "2026-10-01", "2026-10-31")).toBe("October 2026");
  });

  it("names a week inside one month", () => {
    expect(periodTitle("week", "2026-10-12", "2026-10-18")).toBe("Oct 12 – 18");
  });

  it("names a week across two months", () => {
    expect(periodTitle("week", "2026-09-28", "2026-10-04")).toBe("Sep 28 – Oct 4");
  });
});

describe("calendarDayLabel", () => {
  it("says one activity and its type", () => {
    expect(calendarDayLabel(day({ activity_count: 1, primary_activity_type: "run" }))).toBe(
      "Wednesday, October 14: 1 activity, a run.",
    );
  });

  it("counts several activities and names the longest", () => {
    expect(
      calendarDayLabel(day({ activity_count: 2, primary_activity_type: "strength" })),
    ).toBe("Wednesday, October 14: 2 activities, the longest a strength session.");
  });

  it("calls an unknown type a workout", () => {
    expect(calendarDayLabel(day({ activity_count: 1, primary_activity_type: "other" }))).toBe(
      "Wednesday, October 14: 1 activity, a workout.",
    );
  });

  it("names recovery, rest and future days", () => {
    expect(calendarDayLabel(day({ recovery: true }))).toBe("Wednesday, October 14: recovery day.");
    expect(calendarDayLabel(day())).toBe("Wednesday, October 14: no activity.");
    expect(calendarDayLabel(day({ future: true }))).toBe("Wednesday, October 14: not yet.");
  });
});
