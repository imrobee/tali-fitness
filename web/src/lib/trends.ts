// Words and bar scaling for the trend cards. The numbers (including the change against
// the period before) come from the server; this file only phrases and scales them.

import type { Grain, NutritionPeriod, NutritionTrend, PeriodStatus, TrainingPeriod } from "../api/types";
import { formatDistance } from "./activities";
import { parseIsoDate } from "./dates";
import { formatDuration, formatNumber } from "./format";

/** The Week / Month switch, shared by the calendar and both trend cards. */
export const GRAIN_OPTIONS: { value: Grain; text: string }[] = [
  { value: "week", text: "Week" },
  { value: "month", text: "Month" },
];

function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** Two-line x label: week "Oct" over "12" (its Monday); month "Oct" over "26". */
export function periodAxis(grain: Grain, start: string): [string, string] {
  const date = parseIsoDate(start);
  const month = date.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" });
  if (grain === "week") return [month, String(date.getUTCDate())];
  return [month, `’${String(date.getUTCFullYear()).slice(2)}`];
}

/** "week of October 12" or "October 2026", for spoken labels. */
export function periodName(grain: Grain, start: string): string {
  const date = parseIsoDate(start);
  if (grain === "week") {
    const day = date.toLocaleDateString("en-US", { month: "long", day: "numeric", timeZone: "UTC" });
    return `week of ${day}`;
  }
  return date.toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
}

/** The top of a trend chart: room above the tallest bar or the reference line. Never 0. */
export function trendMax(values: (number | null)[], reference: number | null = null): number {
  const tallest = Math.max(0, ...values.map((v) => v ?? 0));
  return Math.max(1.15 * tallest, 1.25 * (reference ?? 0), 1);
}

/** "up 20%", "down 25%", "the same as"; null when there is nothing to compare with. */
export function changeWords(pct: number | null): string | null {
  if (pct === null) return null;
  if (pct === 0) return "the same as";
  return pct > 0 ? `up ${pct}% on` : `down ${Math.abs(pct)}% on`;
}

/** The last finished period: the newest one is still running. */
export function lastComplete<T extends { current: boolean }>(periods: T[]): T | undefined {
  return periods.filter((p) => !p.current).at(-1);
}

// --- training ------------------------------------------------------------------------------

function trainingAmount(period: TrainingPeriod): string {
  return `${count(period.sessions, "session", "sessions")}, ${formatDuration(period.active_s)}`;
}

/** "Last week: 4 sessions, 3 h 10 min, up 20% on the week before." */
export function trainingHeadline(periods: TrainingPeriod[], grain: Grain): string {
  const last = lastComplete(periods);
  const name = grain === "week" ? "week" : "month";
  if (!last) return "";
  if (last.sessions === 0) return `No training last ${name}.`;
  const change = changeWords(last.active_change_pct);
  const tail = change ? `, ${change} the ${name} before` : "";
  return `Last ${name}: ${trainingAmount(last)}${tail}.`;
}

/** "This week so far: 1 session, 30 min." */
export function trainingSoFar(periods: TrainingPeriod[], grain: Grain): string {
  const current = periods.find((p) => p.current);
  if (!current) return "";
  const name = grain === "week" ? "This week" : "This month";
  if (current.sessions === 0) return `${name} so far: no training yet.`;
  return `${name} so far: ${trainingAmount(current)}.`;
}

/** "Running 12.5 km · Lifting 3,491 kg", leaving out what is 0. */
export function trainingDetail(period: TrainingPeriod): string {
  const parts: string[] = [];
  if (period.run_m > 0) parts.push(`Running ${formatDistance(period.run_m)}`);
  if (period.volume_kg > 0) parts.push(`Lifting ${formatNumber(period.volume_kg)} kg`);
  return parts.join(" · ");
}

/** "Week of October 12: 4 sessions, 3 h 10 min." plus "so far" while it runs. */
export function trainingBarLabel(period: TrainingPeriod, grain: Grain): string {
  const name = periodName(grain, period.start);
  const label = name.charAt(0).toUpperCase() + name.slice(1);
  const soFar = period.current ? " so far" : "";
  if (period.sessions === 0) return `${label}${soFar}: no training.`;
  return `${label}${soFar}: ${trainingAmount(period)}.`;
}

// --- nutrition -----------------------------------------------------------------------------

/** "7-day average: 1,742 kcal and 112 g protein a day, over 6 logged days." */
export function rollingLine(rolling: NutritionTrend["rolling_7d"]): string {
  if (rolling.kcal_avg === null) return "Nothing logged in the last 7 days.";
  const protein = rolling.protein_avg_g === null ? "" : ` and ${rolling.protein_avg_g} g protein`;
  const days = count(rolling.days_logged, "logged day", "logged days");
  return `7-day average: ${formatNumber(rolling.kcal_avg)} kcal${protein} a day, over ${days}.`;
}

/** "Last week: 1,850 kcal a day, 4 of 5 logged days within budget." */
export function nutritionHeadline(periods: NutritionPeriod[], grain: Grain): string {
  const last = lastComplete(periods);
  const name = grain === "week" ? "week" : "month";
  if (!last) return "";
  if (last.avg_kcal === null) return `Nothing logged last ${name}.`;
  const average = `Last ${name}: ${formatNumber(last.avg_kcal)} kcal a day`;
  if (last.status === "not_set") return `${average}, no budget set.`;
  return `${average}, ${last.days_within} of ${count(last.days_logged, "logged day", "logged days")} within budget.`;
}

const STATUS_WORDS: Record<PeriodStatus, string> = {
  within: "within budget on average",
  over: "over budget on average",
  not_set: "no budget set",
  not_logged: "nothing logged",
};

/** "Week of October 12: 1,850 kcal a day, within budget on average." */
export function nutritionBarLabel(period: NutritionPeriod, grain: Grain): string {
  const name = periodName(grain, period.start);
  const label = name.charAt(0).toUpperCase() + name.slice(1);
  const soFar = period.current ? " so far" : "";
  if (period.avg_kcal === null) return `${label}${soFar}: ${STATUS_WORDS.not_logged}.`;
  return `${label}${soFar}: ${formatNumber(period.avg_kcal)} kcal a day, ${STATUS_WORDS[period.status]}.`;
}
