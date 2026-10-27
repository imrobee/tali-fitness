import { describe, expect, it } from "vitest";
import { RING_RADIUS, RING_SIZE, RING_STROKE, ringArc, ringTone, trianglePoints } from "./streakRing";

describe("calorie ring", () => {
  it("leaves a visible gap around the 32px circle and stays inside its square", () => {
    expect(RING_RADIUS - RING_STROKE / 2 - 16).toBeGreaterThanOrEqual(2);
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
