// Pure helpers for the Me page's "Data and sync" panel (UI_SPEC.md 6.3). No React here.

export type SourceStatus = "ok" | "delayed" | "failed";

const STATUS_TEXT: Record<SourceStatus, string> = {
  ok: "OK",
  delayed: "Delayed",
  failed: "Failed",
};

/** The word shown next to the status icon, so the status never depends on colour. */
export function statusLabel(status: SourceStatus): string {
  return STATUS_TEXT[status];
}

const SOURCE_NAME: Record<string, string> = {
  strava: "Strava",
  health: "Apple Health",
};

export function sourceName(source: string): string {
  return SOURCE_NAME[source] ?? source;
}

/** "just now", "12 min ago", "1 hour ago", "9 hours ago", "3 days ago". */
export function timeAgo(iso: string, now: number): string {
  const minutes = Math.floor((now - Date.parse(iso)) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  return `${days} days ago`;
}

const CLOCK = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Manila",
  weekday: "short",
  hour: "numeric",
  minute: "2-digit",
});

/** The clock time in the app's time zone, e.g. "Tue 15:04". */
export function clockTime(iso: string): string {
  return CLOCK.format(new Date(iso));
}

/** Reasons from the API, in the words the panel shows. */
const REASON_TEXT: Record<string, string> = {
  invalid_sample: "Invalid health sample",
  unknown_type: "Unknown type",
  bad_unit: "Unexpected unit",
  out_of_range: "Value out of range",
  outside_window: "Outside the date window",
  bad_timestamp: "Bad timestamp",
  unparsed_line: "Line not understood",
  empty_exercise: "Exercise with no sets",
};

export function reasonLabel(code: string): string {
  return REASON_TEXT[code] ?? code;
}
