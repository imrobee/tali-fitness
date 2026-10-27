// The calorie ring around each streak circle (UI_SPEC.md 5.3). Pure geometry, no React.
// Grey: no food logged yet. Green: within budget (or no budget set). Orange: over budget,
// drawn with a gap at the bottom that holds a small triangle, so "over" never relies on
// colour alone.

import type { CalorieStatus } from "./ring";

export type RingTone = "grey" | "green" | "orange";

export const RING_SIZE = 42; // the square the ring is drawn in, around a 32px circle
export const RING_STROKE = 2.5;
// The ring's inner edge is 2.5px clear of the 16px circle (19.75 - 1.25 = 18.5), and its
// outer edge touches the square (19.75 + 1.25 = 21).
export const RING_RADIUS = 19.75;
const GAP_DEGREES = 50; // room at the bottom for the triangle

/** The small triangle in an over-budget ring's gap, pointing up, centred on the ring line. */
export function trianglePoints(centre: number): string {
  const x = centre;
  const y = centre + RING_RADIUS;
  return `${x},${y - 3} ${x - 3},${y + 2} ${x + 3},${y + 2}`;
}

export function ringTone(status: CalorieStatus): RingTone {
  if (status === "over") return "orange";
  if (status === "not_logged") return "grey";
  return "green"; // within, or logged without a budget: nothing to be over
}

export interface RingArc {
  /** stroke-dasharray: the drawn length, then the gap. Null for a full circle. */
  dasharray: string | null;
  /** Rotation (degrees) that centres the gap at six o'clock. */
  rotate: number;
}

/**
 * SVG strokes a circle from three o'clock, clockwise. With a dash of (C - gap) and a gap of
 * `gap`, the gap ends where the stroke started; rotating by 90 + GAP/2 puts its middle at
 * six o'clock (90 degrees, clockwise from three on screen).
 */
export function ringArc(tone: RingTone): RingArc {
  if (tone !== "orange") return { dasharray: null, rotate: 0 };
  const circumference = 2 * Math.PI * RING_RADIUS;
  const gap = (GAP_DEGREES / 360) * circumference;
  return {
    dasharray: `${(circumference - gap).toFixed(2)} ${gap.toFixed(2)}`,
    rotate: 90 + GAP_DEGREES / 2,
  };
}
