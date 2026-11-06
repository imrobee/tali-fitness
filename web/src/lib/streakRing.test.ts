import { describe, expect, it } from "vitest";
import { CIRCLE_SIZE, circleLook, strungToNext, RING_RADIUS, RING_SIZE, RING_STROKE, ringArc, ringTone, trianglePoints } from "./streakRing";

describe("calorie ring", () => {
  it("leaves a clear gap around the circle and stays inside its square", () => {
    expect(RING_RADIUS - RING_STROKE / 2 - CIRCLE_SIZE / 2).toBeGreaterThanOrEqual(4);
    expect(RING_RADIUS + RING_STROKE / 2).toBeLessThanOrEqual(RING_SIZE / 2);
  });

  it("puts the triangle on the ring line at six o'clock", () => {
    expect(trianglePoints(21)).toBe("21,37.75 18,42.75 24,42.75");
  });

  it("has three tones; a day logged without a budget is green", () => {
    expect(ringTone("not_logged")).toBe("grey");
    expect(ringTone("within")).toBe("green");
    expect(ringTone("not_set")).toBe("green");
    expect(ringTone("over")).toBe("orange");
  });

  it("is a full circle unless over budget", () => {
    expect(ringArc("green")).toEqual({ dasharray: null, rotate: 0 });
  });

  it("leaves a gap centred at the bottom when over budget", () => {
    const { dasharray, rotate } = ringArc("orange");
    const [drawn, gap] = (dasharray ?? "").split(" ").map(Number);

    expect(drawn + gap).toBeCloseTo(2 * Math.PI * RING_RADIUS, 1);
    expect(gap / (drawn + gap)).toBeCloseTo(50 / 360, 2);
    // The gap runs from rotate - 50 to rotate degrees: its middle is 90, six o'clock.
    expect(rotate - 50 / 2).toBe(90);
  });
});

describe("streak circle", () => {
  const TODAY = "2026-10-27";
  const base = { date: TODAY, state: "pending", kind: "recovery", recovery_logged: false, primary_activity_type: null };

  it("draws today as an open day, not a rest day, until a recovery day is logged", () => {
    expect(circleLook(base, TODAY)).toBe("today");
    expect(circleLook({ ...base, recovery_logged: true }, TODAY)).toBe("recovery");
    expect(circleLook({ ...base, primary_activity_type: "run" }, TODAY)).toBe("active");
  });

  it("keeps the snowflake for a past rest day and the dashed edge for an at-risk one", () => {
    const yesterday = { ...base, date: "2026-10-26", state: "counted" };
    expect(circleLook(yesterday, TODAY)).toBe("recovery");
    expect(circleLook({ ...yesterday, state: "at_risk", kind: "miss" }, TODAY)).toBe("at_risk");
    expect(circleLook({ ...yesterday, state: "broken", kind: "miss" }, TODAY)).toBe("missed");
    expect(circleLook({ ...yesterday, date: "2026-10-28", state: "future", kind: null }, TODAY)).toBe("future");
  });
});

describe("strungToNext", () => {
  const week = [true, true, false, true, true, true, false].map((in_streak) => ({ in_streak }));

  it("joins two neighbours that are both in the streak", () => {
    expect(week.map((_, index) => strungToNext(week, index))).toEqual([
      true, // Monday to Tuesday
      false, // Tuesday to a day that doesn't count
      false,
      true,
      true,
      false, // Saturday to a Sunday that doesn't count yet
      false, // Sunday: nothing after it on this card
    ]);
  });
});
