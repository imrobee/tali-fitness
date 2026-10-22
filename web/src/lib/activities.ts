// Pure formatting for the Activities page (UI_SPEC.md 6.1). Pace, set lines and summaries
// are worked out here from the API's numbers; the page only lays them out.

import { addDays, parseIsoDate } from "./dates";
import { formatDuration, formatNumber } from "./format";
import { volume, type WeightUnit, weightNumber } from "./units";

export interface ActivitySummaryData {
  type: string;
  duration_s: number;
  moving_s: number | null;
  distance_m: number | null;
  exercise_count: number;
  set_count: number;
  volume_kg: number;
}

export interface SetData {
  kind: string;
  weight_kg: number | null;
  orig_weight: number | null;
  orig_unit: string | null;
  reps: number | null;
  distance_m: number | null;
  duration_s: number | null;
}

const TIME = new Intl.DateTimeFormat("en-US", {
  timeZone: "Asia/Manila",
  hour: "numeric",
  minute: "2-digit",
});

/** A value with at most one decimal, without a trailing ".0": 22.5 -> "22.5", 40 -> "40". */
export function formatDecimal(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/** 21000 -> "21 km", 5230 -> "5.2 km", 800 -> "800 m". */
export function formatDistance(meters: number): string {
  if (meters < 1000) return `${formatNumber(meters)} m`;
  return `${formatDecimal(Math.round(meters / 100) / 10)} km`;
}

/** Seconds per kilometre as "5:41 /km". */
export function formatPace(distanceM: number, seconds: number): string {
  const perKm = Math.round(seconds / (distanceM / 1000));
  return `${Math.floor(perKm / 60)}:${String(perKm % 60).padStart(2, "0")} /km`;
}

/** Seconds as "45 s", "1 min 30 s" (timed sets). */
export function formatSeconds(seconds: number): string {
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest === 0 ? `${minutes} min` : `${minutes} min ${rest} s`;
}

/** "7:10 am – 8:05 am", in the app's time zone. */
export function timeRange(startedAt: string, durationS: number): string {
  const start = new Date(startedAt);
  const end = new Date(start.getTime() + durationS * 1000);
  return `${TIME.format(start).toLowerCase()} – ${TIME.format(end).toLowerCase()}`;
}

/**
 * The one line under an activity's title. Strength lists its volume only when it is not 0;
 * a strength session with no sets read (no Hevy text) falls back to its duration.
 */
export function activitySummary(activity: ActivitySummaryData, unit: WeightUnit = "kg"): string {
  if (activity.type === "strength" && activity.set_count > 0) {
    const parts = [
      plural(activity.exercise_count, "exercise"),
      plural(activity.set_count, "set"),
    ];
    if (activity.volume_kg > 0) parts.push(volume(activity.volume_kg, unit));
    return parts.join(" · ");
  }
  const parts: string[] = [];
  if (activity.distance_m) {
    parts.push(formatDistance(activity.distance_m));
    if (activity.type === "run") {
      parts.push(formatPace(activity.distance_m, activity.moving_s ?? activity.duration_s));
    }
  }
  parts.push(formatDuration(activity.duration_s));
  return parts.join(" · ");
}

/** "Set 1  20 kg × 8", the line for each set (UI_SPEC 6.1). */
export function setLine(number: number, set: SetData, unit: WeightUnit = "kg"): string {
  return `Set ${number}  ${setMeasure(set, unit)}`;
}

/**
 * The measure part of a set line: "20 kg × 8", "10 reps", "1 min 30 s". The weight is in
 * the person's unit; a set entered in the other unit also shows what was typed, exactly:
 * "18.1 kg (40 lb) × 12", or in pounds "44.1 lb (20 kg) × 8".
 */
export function setMeasure(set: SetData, unit: WeightUnit = "kg"): string {
  switch (set.kind) {
    case "weight_reps": {
      const entered = set.orig_unit === unit && set.orig_weight !== null;
      const shown = entered
        ? `${formatDecimal(set.orig_weight ?? 0)} ${unit}`
        : `${weightNumber(set.weight_kg ?? 0, unit)} ${unit}`;
      const original =
        !entered && set.orig_unit !== null && set.orig_weight !== null
          ? ` (${formatDecimal(set.orig_weight)} ${set.orig_unit})`
          : "";
      return `${shown}${original} × ${set.reps}`;
    }
    case "reps":
      return `${set.reps} reps`;
    case "distance_duration":
      return `${formatDistance(set.distance_m ?? 0)} · ${formatDuration(set.duration_s ?? 0)}`;
    default:
      return formatSeconds(set.duration_s ?? 0);
  }
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

/** "Sat, Oct 17": the day heading in the Activities list (UI_SPEC.md 6.1). */
export function dayHeading(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** The chip beside a heading: "Today", "Yesterday", or nothing for older days. */
export function dayChip(iso: string, today: string): string | null {
  if (iso === today) return "Today";
  if (iso === addDays(today, -1)) return "Yesterday";
  return null;
}
