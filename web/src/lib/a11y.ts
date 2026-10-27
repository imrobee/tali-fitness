// Accessible names (UI_SPEC.md section 8). Each streak circle with its calorie ring is
// one element with one spoken label; the ring and the protein bar read as sentences.

import { days, formatNumber, longDate } from "./format";
import type { CalorieStatus } from "./ring";

const KIND_WORDS: Record<string, string> = {
  success: "workout and food within budget",
  over: "over budget",
  recovery: "rest day",
  miss: "nothing logged",
};

const STATE_WORDS: Record<string, string> = {
  counted: "streak kept",
  pending: "today, not counted yet",
  at_risk: "can still be filled in until midnight",
  broken: "streak ended",
  future: "upcoming",
};

const CALORIE_WORDS: Record<string, string> = {
  not_logged: "not logged",
  not_set: "logged, no budget set",
  within: "within budget",
  over: "over budget",
};

export function streakDayLabel(day: {
  date: string;
  state: string;
  kind: string | null;
  calorie_status: string;
}): string {
  if (day.state === "future") return `${longDate(day.date)}: upcoming.`;
  const kind = KIND_WORDS[day.kind ?? "miss"] ?? day.kind;
  const state = STATE_WORDS[day.state] ?? day.state;
  const calories = CALORIE_WORDS[day.calorie_status] ?? day.calorie_status;
  return `${longDate(day.date)}: ${kind}, ${state}. Calories: ${calories}.`;
}

export function streakSummary(count: number, todayState: string | undefined, atRisk: boolean) {
  const today = todayState === "counted" ? "counted" : "not counted yet";
  const risk = atRisk ? " Yesterday can still be filled in." : "";
  return `Streak: ${days(count)}. Today: ${today}.${risk}`;
}

export function calorieLabel(eaten: number, budget: number | null, status: CalorieStatus) {
  if (budget === null) return `Calories: ${formatNumber(eaten)} eaten, no budget set.`;
  if (status === "over") {
    return `Calories: ${formatNumber(eaten)} eaten of ${formatNumber(budget)}, ${formatNumber(
      eaten - budget,
    )} over budget.`;
  }
  return `Calories: ${formatNumber(eaten)} eaten of ${formatNumber(budget)}, ${formatNumber(
    budget - eaten,
  )} left.`;
}

export function proteinLabel(grams: number, goal: number | null, percent: number | null) {
  if (goal === null || percent === null) return `Protein: ${grams} grams, no goal set.`;
  return `Protein: ${grams} of ${goal} grams, ${percent} percent.`;
}
