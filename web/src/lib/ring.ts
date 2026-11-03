// Calorie ring geometry and content (UI_SPEC.md 5.6). Pure, unit tested in ring.test.ts.
//
// The ring is one SVG circle drawn with stroke-dasharray: the visible arc is
// circumference * fraction. Within budget it fills by eaten / budget. Over budget it is
// full and orange, and the centre says "kcal over" (Rob removed the dashed overflow arc).

export type CalorieStatus = "not_logged" | "not_set" | "within" | "over";

export interface RingContent {
  fill: number; // 0..1 of the arc
  tone: "within" | "over" | "empty";
  figure: number | null; // the big number in the centre
  caption: string; // under the figure
}

export function ringContent(
  eaten: number,
  budget: number | null,
  status: CalorieStatus,
): RingContent {
  if (budget === null) {
    return { fill: 0, tone: "empty", figure: null, caption: "No budget set" };
  }
  if (status === "over" || eaten > budget) {
    return { fill: 1, tone: "over", figure: eaten - budget, caption: "kcal over" };
  }
  return {
    fill: Math.min(eaten / budget, 1),
    tone: eaten > 0 ? "within" : "empty",
    figure: budget - eaten,
    caption: "kcal left",
  };
}

export interface Arc {
  circumference: number;
  dashArray: string;
}

/** Dash pattern that shows `fraction` of a circle of `radius`. */
export function arc(radius: number, fraction: number): Arc {
  const circumference = 2 * Math.PI * radius;
  const visible = circumference * Math.max(0, Math.min(fraction, 1));
  return { circumference, dashArray: `${visible} ${circumference}` };
}


/** Protein bar width: the true ratio, capped at 100% (UI_SPEC.md 5.7). */
export function proteinFill(grams: number, goal: number | null): number {
  if (!goal) return 0;
  return Math.max(0, Math.min(grams / goal, 1));
}
