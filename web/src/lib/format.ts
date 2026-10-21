// Display formatting. Pure functions, unit tested in format.test.ts.

import { addDays, parseIsoDate } from "./dates";

const numberFormat = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

/** 1853 -> "1,853" */
export function formatNumber(value: number): string {
  return numberFormat.format(Math.round(value));
}

/** Seconds -> "32 min", "1 h", "1 h 05 min" (UI_SPEC.md 5.5). */
export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes} min`;
  if (minutes === 0) return `${hours} h`;
  return `${hours} h ${String(minutes).padStart(2, "0")} min`;
}

/** "Today", "Yesterday", or "Sat, Oct 17" for the day chooser. */
export function dayLabel(iso: string, today: string): string {
  if (iso === today) return "Today";
  if (iso === addDays(today, -1)) return "Yesterday";
  return parseIsoDate(iso).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "Tuesday, October 13" for accessible names. */
export function longDate(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "Good afternoon, Rob", or just the greeting without a nickname (UI_SPEC.md 5.1). */
export function greetingLine(greeting: string, nickname: string | null): string {
  return nickname ? `${greeting}, ${nickname}` : greeting;
}

/** "1 day", "12 days" */
export function days(count: number): string {
  return count === 1 ? "1 day" : `${count} days`;
}
