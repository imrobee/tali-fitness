// Pure scaling and labels for the Calories by day card (UI_SPEC.md 5.8). No React here.

import type { BarStatus, WeekBar } from "../api/types";
import { addDays, parseIsoDate } from "./dates";
import { formatNumber } from "./format";
import { weekRange } from "./progress";

const WEEKDAY = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

/** Two-letter weekday for the x axis: "2026-10-19" -> "Mo". */
export function weekdayLetters(iso: string): string {
  return WEEKDAY[parseIsoDate(iso).getUTCDay()];
}

/** The week the chart shows: "This week" when it holds today, else "Oct 19 – 25". */
export function chartWeekLabel(weekStart: string, today: string): string {
  const weekEnd = addDays(weekStart, 6);
  if (weekStart <= today && today <= weekEnd) return "This week"; // ISO dates compare as strings
  return weekRange(weekStart, weekEnd);
}

/**
 * The top of the chart: a little above the biggest budget, or above the tallest bar if
 * that is higher. Never 0, so an empty week still has a scale.
 */
export function chartMax(bars: WeekBar[]): number {
  const budgets = bars.map((bar) => bar.budget ?? 0);
  const kcals = bars.map((bar) => bar.kcal ?? 0);
  return Math.max(1.25 * Math.max(0, ...budgets), 1.1 * Math.max(0, ...kcals), 1);
}

/** A value as a percentage of the chart height, kept between 0 and 100. */
export function percentOf(value: number, max: number): number {
  return Math.min(100, Math.max(0, (value / max) * 100));
}

/** Whether a day gets a bar at all: future and not-logged days get none (UI_SPEC 5.8). */
export function hasBar(bar: WeekBar): boolean {
  return bar.kcal !== null && bar.status !== "future" && bar.status !== "not_logged";
}

const STATUS_TEXT: Record<BarStatus, string> = {
  within: "within budget",
  over: "over budget",
  not_set: "logged, no budget set",
  not_logged: "not logged",
  future: "not yet",
};

/** The spoken label for one day, e.g. "Tuesday: 2,173 kcal, over budget". */
export function barLabel(bar: WeekBar, dayName: string): string {
  if (!hasBar(bar) || bar.kcal === null) return `${dayName}: ${STATUS_TEXT[bar.status]}`;
  return `${dayName}: ${formatNumber(bar.kcal)} kcal, ${STATUS_TEXT[bar.status]}`;
}

/**
 * The summary for screen readers (UI_SPEC.md 8): "Weekly calories: 4 days within budget,
 * 1 over, budget 1,853." The budget is named only when the whole week shares one.
 */
export function chartSummary(bars: WeekBar[]): string {
  const within = bars.filter((bar) => bar.status === "within").length;
  const over = bars.filter((bar) => bar.status === "over").length;
  const budgets = new Set(bars.map((bar) => bar.budget).filter((b) => b !== null));
  const parts: string[] = [];
  if (within > 0) parts.push(`${within} ${within === 1 ? "day" : "days"} within budget`);
  if (over > 0) parts.push(`${over} over`);
  if (parts.length === 0) return "Weekly calories: no day with calories and a budget yet.";
  const budget = budgets.size === 1 ? `, budget ${formatNumber([...budgets][0] as number)}` : "";
  return `Weekly calories: ${parts.join(", ")}${budget}.`;
}
