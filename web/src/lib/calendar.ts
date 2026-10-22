// Titles and spoken labels for the Activities calendar. No React here.

import type { CalendarDay, CalendarView } from "../api/types";
import { parseIsoDate } from "./dates";
import { longDate } from "./format";

export const WEEKDAY_HEADERS = ["M", "T", "W", "T", "F", "S", "S"];

const TYPE_NAMES: Record<string, string> = {
  run: "run",
  walk: "walk",
  cycle: "ride",
  swim: "swim",
  strength: "strength session",
  yoga: "yoga session",
  hiit: "HIIT session",
};

function monthDay(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "October 2026" for a month; "Oct 12 – 18" or "Sep 28 – Oct 4" for a week. */
export function periodTitle(view: CalendarView, start: string, end: string): string {
  if (view === "month") {
    return parseIsoDate(start).toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    });
  }
  const sameMonth = start.slice(0, 7) === end.slice(0, 7);
  const endText = sameMonth ? String(parseIsoDate(end).getUTCDate()) : monthDay(end);
  return `${monthDay(start)} – ${endText}`;
}

/** "Wednesday, October 14: 2 activities, the longest a strength session." */
export function calendarDayLabel(day: CalendarDay): string {
  const name = longDate(day.date);
  if (day.future) return `${name}: not yet.`;
  if (day.activity_count === 0) {
    return day.recovery ? `${name}: recovery day.` : `${name}: no activity.`;
  }
  const kind = TYPE_NAMES[day.primary_activity_type ?? ""] ?? "workout";
  if (day.activity_count === 1) return `${name}: 1 activity, a ${kind}.`;
  return `${name}: ${day.activity_count} activities, the longest a ${kind}.`;
}
