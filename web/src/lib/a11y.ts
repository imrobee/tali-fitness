// Accessible names (UI_SPEC.md section 8). Each streak circle with its calorie marker is
// one element with one spoken label; the ring and the protein bar read as sentences.

import { days, formatNumber, longDate } from "./format";
import type { CalorieStatus } from "./ring";

const STATE_WORDS: Record<string, string> = {
  qualifying: "qualifying day",
  recovery: "recovery day",
  today_pending: "today, not counted yet",
  at_risk: "not logged yet, can still be filled in",
  missed: "missed",
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
  primary_activity_type: string | null;
  calorie_status: string;
}): string {
  const state = STATE_WORDS[day.state] ?? day.state;
  if (day.state === "future") return `${longDate(day.date)}: ${state}.`;
  const workout = day.primary_activity_type ? "Workout" : "No workout";
  const calories = CALORIE_WORDS[day.calorie_status] ?? day.calorie_status;
  return `${longDate(day.date)}: ${state}. ${workout}. Calories: ${calories}.`;
}

export function streakSummary(count: number, todayState: string | undefined, atRisk: boolean) {
  const today =
    todayState === "qualifying"
      ? "counted"
      : todayState === "recovery"
        ? "recovery day"
        : "not counted yet";
  const risk = atRisk ? " Yesterday isn't logged yet." : "";
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
