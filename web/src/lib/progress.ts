// Words for the progress cards: personal records, muscle volume, and last week's summary.
// The numbers and comparisons come from the server; this file only phrases them.

import type { MuscleWeek, PersonalRecord, WeeklySummary } from "../api/types";
import { formatDistance } from "./activities";
import { parseIsoDate } from "./dates";
import { formatDuration, formatNumber } from "./format";
import { bodyWeight, volume, type WeightUnit, weightNumber } from "./units";

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

/** "Up 5.0 kg on the record before", or null for a first record. */
export function recordGain(record: PersonalRecord, unit: WeightUnit): string | null {
  if (record.prev_e1rm_kg === null) return null;
  return `Up ${bodyWeight(record.e1rm_kg - record.prev_e1rm_kg, unit)} on the record before`;
}

/** The spoken label for one record row. */
export function recordLabel(record: PersonalRecord, unit: WeightUnit): string {
  const isNew = record.recent ? "New record. " : "";
  const gain = recordGain(record, unit);
  return `${isNew}${record.exercise}: estimated one-rep max ${recordValue(record, unit)}. ${recordSet(record, unit)}.${gain ? ` ${gain}.` : ""}`;
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

// --- weekly summary ------------------------------------------------------------------------

export interface SummaryRow {
  label: string;
  value: string;
  change: string | null;
}

function countChange(now: number, before: number | null): string | null {
  if (before === null) return null;
  const delta = now - before;
  if (delta === 0) return "same";
  return `${delta > 0 ? "+" : "−"}${Math.abs(delta)}`;
}

function percentChange(now: number, before: number | null): string | null {
  if (before === null || before === 0) return null;
  const pct = Math.round((100 * (now - before)) / before);
  if (pct === 0) return "same";
  return pct > 0 ? `up ${pct}%` : `down ${Math.abs(pct)}%`;
}

function amountChange(now: number | null, before: number | null, text: (n: number) => string) {
  if (now === null || before === null) return null;
  const delta = now - before;
  if (Math.abs(delta) < 0.05) return "same";
  return `${delta > 0 ? "+" : "−"}${text(Math.abs(delta))}`;
}

/** The rows of the "Last week" card, leaving out what is 0 or not logged. */
export function summaryRows(s: WeeklySummary, unit: WeightUnit): SummaryRow[] {
  const rows: SummaryRow[] = [
    {
      label: "Days counted",
      value: `${s.qualifying_days} of 7`,
      change: countChange(s.qualifying_days, s.prev_qualifying_days),
    },
    { label: "Sessions", value: String(s.sessions), change: countChange(s.sessions, s.prev_sessions) },
  ];
  if (s.active_s > 0) {
    rows.push({ label: "Active time", value: formatDuration(s.active_s), change: percentChange(s.active_s, s.prev_active_s) });
  }
  if (s.run_m > 0) rows.push({ label: "Running", value: formatDistance(s.run_m), change: null });
  if (s.volume_kg > 0) rows.push({ label: "Lifting", value: volume(s.volume_kg, unit), change: null });
  if (s.avg_kcal !== null) {
    rows.push({
      label: "Calories a day",
      value: `${formatNumber(s.avg_kcal)} kcal`,
      change: amountChange(s.avg_kcal, s.prev_avg_kcal, (n) => `${formatNumber(n)} kcal`),
    });
  }
  if (s.avg_protein_g !== null) {
    rows.push({ label: "Protein a day", value: `${formatNumber(s.avg_protein_g)} g`, change: null });
  }
  if (s.avg_weight_kg !== null) {
    rows.push({
      label: "Average weight",
      value: bodyWeight(s.avg_weight_kg, unit),
      change: amountChange(s.avg_weight_kg, s.prev_avg_weight_kg, (n) => bodyWeight(n, unit)),
    });
  }
  return rows;
}
