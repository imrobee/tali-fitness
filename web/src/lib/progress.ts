// Words for the progress cards: personal records and muscle volume.
// The numbers and comparisons come from the server; this file only phrases them.

import type { MuscleWeek, PersonalRecord } from "../api/types";
import { parseIsoDate } from "./dates";
import { volume, type WeightUnit, weightNumber } from "./units";

function monthDay(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

/** "Oct 12 – 18" or "Sep 28 – Oct 4". */
export function weekRange(start: string, end: string): string {
  const sameMonth = start.slice(0, 7) === end.slice(0, 7);
  return `${monthDay(start)} – ${sameMonth ? parseIsoDate(end).getUTCDate() : monthDay(end)}`;
}

// --- personal records ----------------------------------------------------------------------

/** "58.3 kg": the estimated one-rep max. */
export function recordValue(record: PersonalRecord, unit: WeightUnit): string {
  return `${weightNumber(record.e1rm_kg, unit)} ${unit}`;
}

/** "From 50 kg × 5 on Oct 13": the set that set the record. */
export function recordSet(record: PersonalRecord, unit: WeightUnit): string {
  return `From ${weightNumber(record.weight_kg, unit)} ${unit} × ${record.reps} on ${monthDay(record.date)}`;
}

/** The spoken label for one record row: what the row shows, with the value named. */
export function recordLabel(record: PersonalRecord, unit: WeightUnit): string {
  return `${record.exercise}: estimated one-rep max ${recordValue(record, unit)}. ${recordSet(record, unit)}.`;
}

// --- muscle volume -------------------------------------------------------------------------

function signed(delta: number, noun: string): string {
  if (delta === 0) return `same ${noun}s as the week before`;
  const n = Math.abs(delta);
  return `${delta > 0 ? "+" : "−"}${n} ${noun}${n === 1 ? "" : "s"} on the week before`;
}

/** "6 sets · 1,000 kg". Bodyweight-only groups show sets alone. */
export function muscleAmount(group: MuscleWeek, unit: WeightUnit): string {
  const sets = `${group.sets} ${group.sets === 1 ? "set" : "sets"}`;
  return group.volume_kg > 0 ? `${sets} · ${volume(group.volume_kg, unit)}` : sets;
}

export function muscleChange(group: MuscleWeek): string {
  return signed(group.sets - group.prev_sets, "set");
}
