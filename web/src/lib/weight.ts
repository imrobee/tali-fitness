// Words and chart scaling for the weight card (UI_SPEC.md 6.2). The averages, change and
// goal come from the server; this file only phrases and places them. No React here.

import type { Weight, WeightDay } from "../api/types";
import { longDate } from "./format";
import { parseIsoDate } from "./dates";
import { bodyWeight, fromKg, type WeightUnit } from "./units";


function shortDate(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** The one line under the title: the latest weigh-in and the 7-day average. */
export function weightHeadline(weight: Weight, unit: WeightUnit = "kg"): string {
  if (weight.latest_kg === null || weight.latest_date === null) {
    return "No weigh-ins in these days yet.";
  }
  const average =
    weight.avg_7d_kg === null ? "" : `, 7-day average ${bodyWeight(weight.avg_7d_kg, unit)}`;
  return `Latest ${bodyWeight(weight.latest_kg, unit)} on ${shortDate(weight.latest_date)}${average}.`;
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
    weightHeadline(weight, unit),
    changeLine(weight.change_7d_kg, unit),
    goalLine(weight, unit),
  ];
  return parts.filter((part): part is string => part !== null).join(" ");
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
  return count <= 1 ? width / 2 : (index / (count - 1)) * width;
}
