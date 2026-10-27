import { describe, expect, it } from "vitest";
import {
  activitySummary,
  dayChip,
  dayHeading,
  formatDecimal,
  formatDistance,
  formatPace,
  formatSeconds,
  setLine,
  timeRange,
} from "./activities";

describe("distances and pace", () => {
  it("shows metres under a kilometre and one decimal above", () => {
    expect(formatDistance(800)).toBe("800 m");
    expect(formatDistance(5230)).toBe("5.2 km");
    expect(formatDistance(21000)).toBe("21 km");
  });

  it("gives pace per kilometre as minutes and seconds", () => {
    // 5 km in 28 min 25 s is 5:41 per km.
    expect(formatPace(5000, 28 * 60 + 25)).toBe("5:41 /km");
  });
});

describe("setLine", () => {
  it("writes each set kind the way UI_SPEC 6.1 does", () => {
    expect(
      setLine(1, {
        kind: "weight_reps",
        weight_kg: 20,
        orig_weight: 20,
        orig_unit: "kg",
        reps: 8,
        distance_m: null,
        duration_s: null,
      }),
    ).toBe("Set 1  20 kg × 8");

    expect(
      setLine(2, {
        kind: "weight_reps",
        weight_kg: 18.14369,
        orig_weight: 40,
        orig_unit: "lb",
        reps: 12,
        distance_m: null,
        duration_s: null,
      }),
    ).toBe("Set 2  18.1 kg (40 lb) × 12");

    expect(
      setLine(3, { kind: "reps", weight_kg: null, orig_weight: null, orig_unit: null, reps: 10, distance_m: null, duration_s: null }),
    ).toBe("Set 3  10 reps");

    expect(
      setLine(4, {
        kind: "distance_duration",
        weight_kg: null,
        orig_weight: null,
        orig_unit: null,
        reps: null,
        distance_m: 21000,
        duration_s: 3600,
      }),
    ).toBe("Set 4  21 km · 1 h");

    expect(
      setLine(5, { kind: "duration", weight_kg: null, orig_weight: null, orig_unit: null, reps: null, distance_m: null, duration_s: 90 }),
    ).toBe("Set 5  1 min 30 s");
  });
});

describe("activitySummary", () => {
  const base = {
    type: "run",
    duration_s: 1740, // 29 min elapsed
    moving_s: 1700, // 28 min 20 s moving: 5:25 /km on moving time

    distance_m: 5230,
    exercise_count: 0,
    set_count: 0,
    volume_kg: 0,
  };

  it("shows distance, pace and time for a run, pacing on moving time", () => {
    expect(activitySummary(base)).toBe("5.2 km · 5:25 /km · 29 min");
  });

  it("falls back to elapsed time when there is no moving time", () => {
    expect(activitySummary({ ...base, moving_s: null })).toBe("5.2 km · 5:33 /km · 29 min");
  });

  it("lists exercises, sets and volume for strength", () => {
    expect(
      activitySummary({ ...base, type: "strength", distance_m: null, exercise_count: 9, set_count: 22, volume_kg: 3490.9 }),
    ).toBe("9 exercises · 22 sets · 3,491 kg");
  });

  it("drops the volume when it is 0 and uses singular counts", () => {
    expect(
      activitySummary({ ...base, type: "strength", distance_m: null, exercise_count: 1, set_count: 1, volume_kg: 0 }),
    ).toBe("1 exercise · 1 set");
  });

  it("shows the duration for a strength session with no sets read", () => {
    expect(activitySummary({ ...base, type: "strength", distance_m: null, duration_s: 3840 })).toBe("1 h 04 min");
  });

  it("shows only the duration for an activity with no distance", () => {
    expect(activitySummary({ ...base, type: "yoga", distance_m: null, duration_s: 2700 })).toBe("45 min");
  });
});

describe("timeRange and small helpers", () => {
  it("shows the start and end in Manila time", () => {
    // 02:10 UTC is 10:10 in Manila; 30 minutes later.
    expect(timeRange("2026-10-20T02:10:00Z", 1800)).toBe("10:10 am – 10:40 am");
  });

  it("formats timed sets and decimals", () => {
    expect(formatSeconds(45)).toBe("45 s");
    expect(formatSeconds(120)).toBe("2 min");
    expect(formatDecimal(22.5)).toBe("22.5");
    expect(formatDecimal(40)).toBe("40");
  });
});

describe("day headings", () => {
  it("writes the day and marks today and yesterday", () => {
    expect(dayHeading("2026-10-17")).toBe("Sat, Oct 17");
    expect(dayChip("2026-10-20", "2026-10-20")).toBe("Today");
    expect(dayChip("2026-10-19", "2026-10-20")).toBe("Yesterday");
    expect(dayChip("2026-10-17", "2026-10-20")).toBeNull();
  });
});

describe("sets and volume in pounds", () => {
  const kgSet = { kind: "weight_reps", weight_kg: 20, orig_weight: 20, orig_unit: "kg", reps: 8, distance_m: null, duration_s: null } as const;
  const lbSet = { kind: "weight_reps", weight_kg: 18.14369, orig_weight: 40, orig_unit: "lb", reps: 12, distance_m: null, duration_s: null } as const;

  it("shows a set typed in pounds exactly, and a kg set converted with what was typed", () => {
    expect(setLine(1, lbSet, "lb")).toBe("Set 1  40 lb × 12");
    expect(setLine(2, kgSet, "lb")).toBe("Set 2  44.1 lb (20 kg) × 8");
  });

  it("shows volume in pounds", () => {
    expect(
      activitySummary(
        { type: "strength", duration_s: 4080, moving_s: null, distance_m: null, exercise_count: 9, set_count: 22, volume_kg: 3490.9 },
        "lb",
      ),
    ).toBe("9 exercises · 22 sets · 7,696 lb");
  });
});
