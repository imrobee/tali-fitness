// The "How your streak works" card on Me (UI_SPEC.md 6.3), in plain words. It says the same
// as ARCHITECTURE.md section 8 without its internal names, and follows the weekend setting.

import type { RecoveryState } from "../api/types";
import { parseIsoDate } from "./dates";

export function streakRules(lenientWeekends: boolean): string[] {
  return [
    "A day when you log your food, stay within your calorie budget and work out keeps your streak going.",
    "Going over your budget is fine for a day. Two days over budget in a row end the streak.",
    "A rest day is fine too: food logged without a workout, a workout without food logged, or a recovery day logged on the dashboard. Two rest days in a row end the streak.",
    "A day with nothing logged ends the streak.",
    lenientWeekends
      ? "On weekends, only a day with nothing logged ends the streak."
      : "Weekends follow the same rules as weekdays.",
    "During a vacation or injury break, only a day with nothing logged ends the streak.",
    "Today never ends your streak before midnight, and yesterday can still be filled in today.",
  ];
}

function monthDay(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

/** "Oct 12 – 15" for the last break line. */
export function periodText(from: string, to: string): string {
  return from === to ? monthDay(from) : `${monthDay(from)} – ${monthDay(to)}`;
}

/** The text on a date chip: "Mon, Nov 2", or "Choose date" before one is picked. */
export function chipText(iso: string): string {
  if (!iso) return "Choose date";
  return parseIsoDate(iso).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** The form check before saving a break; the server checks the same and more. */
export function vacationError(from: string, to: string): string | null {
  if (!from || !to) return "Pick both dates.";
  if (from > to) return "From must be on or before To.";
  return null;
}

/** The dashboard's recovery card: hidden on a day with an activity, which needs no rest day,
    unless a recovery day was logged anyway, so it can still be undone. */
export function showRecoveryCard(activityCount: number, state: RecoveryState): boolean {
  return activityCount === 0 || state === "logged";
}
