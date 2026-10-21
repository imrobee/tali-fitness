// Calendar dates as "YYYY-MM-DD" strings, exactly as the API sends them.
// The server decides what "today" is (ARCHITECTURE.md section 4); the browser only does
// arithmetic on these strings. Dates are handled in UTC so the phone's own time zone can
// never shift a day.

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function parseIsoDate(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

export function toIsoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(iso: string, days: number): string {
  const date = parseIsoDate(iso);
  date.setUTCDate(date.getUTCDate() + days);
  return toIsoDate(date);
}

/** True for a real calendar date like "2026-10-17" (rejects "2026-02-30"). */
export function isIsoDate(value: string | null): value is string {
  return value !== null && ISO_DATE.test(value) && toIsoDate(parseIsoDate(value)) === value;
}

/** Day of the month for a date circle: "2026-10-07" -> 7. */
export function dayOfMonth(iso: string): number {
  return parseIsoDate(iso).getUTCDate();
}
