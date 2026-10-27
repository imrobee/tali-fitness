import { describe, expect, it } from "vitest";
import type { MuscleWeek, PersonalRecord, WeeklySummary } from "../api/types";
import { muscleAmount, muscleChange, recordGain, recordLabel, recordSet, recordValue, summaryRows, weekRange } from "./progress";

const record: PersonalRecord = {
  exercise: "Incline Bench Press",
  equipment: "Dumbbell",
  muscle_group: "Chest",
  e1rm_kg: 26.25,
  weight_kg: 22.5,
  reps: 6,
  date: "2026-10-17",
  activity_id: 1,
  prev_e1rm_kg: 25.33,
  sessions: 3,
  recent: true,
};

const summary: WeeklySummary = {
  week_start: "2026-10-12",
  week_end: "2026-10-18",
  qualifying_days: 5,
  prev_qualifying_days: 4,
  sessions: 4,
  prev_sessions: 4,
  active_s: 11400,
  prev_active_s: 9500,
  run_m: 12500,
  volume_kg: 0,
  days_logged: 6,
  avg_kcal: 1850,
  prev_avg_kcal: 1900,
  avg_protein_g: 118,
  avg_weight_kg: 74.8,
  prev_avg_weight_kg: 75.1,
};

describe("personal records", () => {
  it("states the estimate, the set it came from and the gain", () => {
    expect(recordValue(record, "kg")).toBe("26.3 kg");
    expect(recordSet(record, "kg")).toBe("From 22.5 kg × 6 on Oct 17");
    expect(recordGain(record, "kg")).toBe("Up 0.9 kg on the record before");
    expect(recordGain({ ...record, prev_e1rm_kg: null }, "kg")).toBeNull();
  });

  it("speaks in the person's unit and says when the record is new", () => {
    expect(recordLabel(record, "lb")).toBe(
      "New record. Incline Bench Press: estimated one-rep max 57.9 lb. From 49.6 lb × 6 on Oct 17. Up 2.0 lb on the record before.",
    );
  });
});

describe("muscle volume", () => {
  const chest: MuscleWeek = { muscle_group: "Chest", sets: 6, volume_kg: 1000, prev_sets: 4, prev_volume_kg: 800 };

  it("gives sets with volume, and sets alone for bodyweight", () => {
    expect(muscleAmount(chest, "kg")).toBe("6 sets · 1,000 kg");
    expect(muscleAmount({ ...chest, sets: 1, volume_kg: 0 }, "kg")).toBe("1 set");
  });

  it("compares sets with the week before", () => {
    expect(muscleChange(chest)).toBe("+2 sets on the week before");
    expect(muscleChange({ ...chest, prev_sets: 7 })).toBe("−1 set on the week before");
    expect(muscleChange({ ...chest, prev_sets: 6 })).toBe("same sets as the week before");
  });
});

describe("weekly summary", () => {
  it("lists what happened with the change, leaving out what is 0", () => {
    expect(summaryRows(summary, "kg")).toEqual([
      { label: "Days counted", value: "5 of 7", change: "+1" },
      { label: "Sessions", value: "4", change: "same" },
      { label: "Active time", value: "3 h 10 min", change: "up 20%" },
      { label: "Running", value: "12.5 km", change: null },
      { label: "Calories a day", value: "1,850 kcal", change: "−50 kcal" },
      { label: "Protein a day", value: "118 g", change: null },
      { label: "Average weight", value: "74.8 kg", change: "−0.3 kg" },
    ]);
  });

  it("shows weight in pounds and names the week", () => {
    const weight = summaryRows(summary, "lb").at(-1);
    expect(weight).toEqual({ label: "Average weight", value: "164.9 lb", change: "−0.7 lb" });
    expect(weekRange("2026-09-28", "2026-10-04")).toBe("Sep 28 – Oct 4");
  });
});
