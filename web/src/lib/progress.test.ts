import { describe, expect, it } from "vitest";
import type { MuscleWeek, PersonalRecord } from "../api/types";
import { muscleAmount, muscleChange, recordDate, recordLabel, recordSet, recordValue, weekRange } from "./progress";

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

describe("personal records", () => {
  it("states the estimate and the set it came from", () => {
    expect(recordValue(record, "kg")).toBe("26.3 kg");
    expect(recordSet(record, "kg")).toBe("From 22.5 kg × 6");
    expect(recordDate(record)).toBe("Oct 17"); // the badge beside the exercise
  });

  it("speaks in the person's unit, without a new-record flag or the gain", () => {
    expect(recordLabel(record, "lb")).toBe(
      "Incline Bench Press: estimated one-rep max 57.9 lb. From 49.6 lb × 6 on Oct 17.",
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

describe("week range", () => {
  it("names a week that crosses a month", () => {
    expect(weekRange("2026-09-28", "2026-10-04")).toBe("Sep 28 – Oct 4");
    expect(weekRange("2026-10-19", "2026-10-25")).toBe("Oct 19 – 25");
  });
});
