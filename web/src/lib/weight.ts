// Words and chart scaling for the weight card (UI_SPEC.md 6.2). The averages, change and
// goal come from the server; this file only phrases and places them. No React here.

import type { Weight, WeightDay } from "../api/types";
import { longDate } from "./format";
import { bodyWeight, fromKg, type WeightUnit, weightNumber } from "./units";

/** The lines under the title, one fact each: "Last weigh-in: 74.8 kg", "7-day average: 74.9 kg". */
export function weightLines(weight: Weight, unit: WeightUnit = "kg"): string[] {
  if (weight.latest_kg === null) return ["No weigh-ins in these days yet."];
  const lines = [`Last weigh-in: ${bodyWeight(weight.latest_kg, unit)}`];
  if (weight.avg_7d_kg !== null) lines.push(`7-day average: ${bodyWeight(weight.avg_7d_kg, unit)}`);
  return lines;
}

/** How the weekly change reads: "Down 0.3 kg on last week." or "No change on last week." */
export function changeLine(changeKg: number | null, unit: WeightUnit = "kg"): string | null {
  if (changeKg === null) return null;
  const rounded = Math.round(fromKg(changeKg, unit) * 10) / 10;
  if (rounded === 0) return "No change on last week.";
  return rounded > 0
    ? `Up ${rounded.toFixed(1)} ${unit} on last week.`
    : `Down ${(-rounded).toFixed(1)} ${unit} on last week.`;
}

/** Distance to the goal, from the 7-day average: "1.5 kg above goal of 72.5 kg". */
export function goalLine(weight: Weight, unit: WeightUnit = "kg"): string {
  if (weight.goal_kg === null) return "Set a weight goal on Me to see how far you are from it.";
  const goal = bodyWeight(weight.goal_kg, unit);
  if (weight.to_goal_kg === null) return `Goal ${goal}.`;
  if (weight.to_goal_kg <= 0) return `At or below your goal of ${goal}.`;
  return `${bodyWeight(weight.to_goal_kg, unit)} above your goal of ${goal}.`;
}

/** The spoken summary for screen readers (UI_SPEC.md 8). */
export function weightSummary(weight: Weight, unit: WeightUnit = "kg"): string {
  const parts = [
    ...weightLines(weight, unit).map((line) => (line.endsWith(".") ? line : `${line}.`)),
    changeLine(weight.change_7d_kg, unit),
    goalLine(weight, unit),
  ];
  return parts.filter((part): part is string => part !== null).join(" ");
}

/** The label printed by a weigh-in's dot: the number alone, in the person's unit ("74.8"). */
export function pointLabel(weightKg: number, unit: WeightUnit = "kg"): string {
  return weightNumber(weightKg, unit);
}

/**
 * Which dots get a printed weight: walking back from the latest weigh-in (always labelled),
 * a dot is labelled only when it is at least `minGap` from the last label, so the numbers
 * never overlap. With a weigh-in every day of 90, most dots stay unlabelled; each still has
 * its spoken label and its title.
 */
export function labelledDots(xs: number[], minGap: number): Set<number> {
  const labelled = new Set<number>();
  let lastX = Infinity;
  for (let i = xs.length - 1; i >= 0; i--) {
    if (lastX - xs[i] >= minGap) {
      labelled.add(i);
      lastX = xs[i];
    }
  }
  return labelled;
}

/**
 * Where the 7-day average line may bend: only on days with a weigh-in, so every rise or fall
 * of the line sits on a real dot. Days without one carry the average over in the data but
 * get no vertex here, so the line runs straight from one weigh-in to the next.
 */
export function averageVertices<T extends Pick<WeightDay, "weight_kg" | "avg_7d_kg">>(
  days: T[],
): { index: number; avgKg: number }[] {
  const vertices: { index: number; avgKg: number }[] = [];
  days.forEach((day, index) => {
    if (day.weight_kg !== null && day.avg_7d_kg !== null) vertices.push({ index, avgKg: day.avg_7d_kg });
  });
  return vertices;
}

/** One day's spoken label: "Monday, October 20: 74.8 kg." */
export function weightDayLabel(day: WeightDay, unit: WeightUnit = "kg"): string {
  if (day.weight_kg === null) return `${longDate(day.date)}: no weigh-in.`;
  return `${longDate(day.date)}: ${bodyWeight(day.weight_kg, unit)}.`;
}

export interface Domain {
  min: number;
  max: number;
}

/**
 * The vertical range of the chart: the lowest and highest value (goal included) with half a
 * kilogram of room on each side, so no point sits on the frame.
 */
export function chartDomain(values: (number | null)[], goal: number | null): Domain {
  const present = values.filter((v): v is number => v !== null);
  if (goal !== null) present.push(goal);
  if (present.length === 0) return { min: 70, max: 80 };
  const low = Math.min(...present);
  const high = Math.max(...present);
  if (high - low < 1) return { min: low - 0.5, max: high + 0.5 };
  return { min: Math.floor(low) - 0.5, max: Math.ceil(high) + 0.5 };
}

/** A kilogram value as a height in pixels: higher weight is higher up the chart. */
export function yFor(value: number, domain: Domain, height: number): number {
  const share = (value - domain.min) / (domain.max - domain.min);
  return height - share * height;
}

/** Day `index` of `count` spread across the width, first day at the left edge. */
export function xFor(index: number, count: number, width: number): number {
  return count <= 1 ? 0 : (index / (count - 1)) * width;
}

/**
 * The days the chart draws: from the first weigh-in to the end of the range. Days before
 * the first weigh-in are left out, so the first point is always at the left edge; with
 * only a few weigh-ins it would otherwise sit at the far right of a 90-day chart.
 */
export function chartDays(days: WeightDay[]): WeightDay[] {
  const first = days.findIndex((day) => day.weight_kg !== null);
  return first === -1 ? [] : days.slice(first);
}
