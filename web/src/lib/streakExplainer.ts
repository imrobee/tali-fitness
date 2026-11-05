// The streak explainer (web/src/streak/explainer.json, DECISIONS D129): its items, and the
// example rows turned into days the streak card's own circle can draw. Pure, no React.

import type { CalorieStatus } from "./ring";
import type { DayKind, DayState, StreakDay } from "../api/types";
import { addDays } from "./dates";
import data from "../streak/explainer.json";

export interface ExplainerExample {
  days: string[];
  break?: number[];
  caption: string;
  expect: { states: string[]; streak: number };
}

export interface ExplainerItem {
  id: string;
  title: string;
  body: string;
  example: ExplainerExample;
}

export const EXPLAINER = data as {
  title: string;
  done: string;
  items: ExplainerItem[];
  targets: { real: string; demo: string };
};

/** The line about targets for this mode: they are effective-dated in the real app, and
    apply to every day in the demo (D122). */
export function targetsLine(demo: boolean): string {
  return demo ? EXPLAINER.targets.demo : EXPLAINER.targets.real;
}

// What each token is, as the card would show it: the workout's icon, the calorie ring,
// and the day's kind (the same letters as pipeline/tests/day_builder.py).
const TOKENS: Record<string, { activity: string | null; calories: CalorieStatus; kind: DayKind }> = {
  S: { activity: "run", calories: "within", kind: "success" },
  O: { activity: "strength", calories: "over", kind: "over" },
  Ov: { activity: null, calories: "over", kind: "over" },
  R: { activity: null, calories: "within", kind: "recovery" },
  A: { activity: "strength", calories: "not_logged", kind: "recovery" },
  M: { activity: null, calories: "not_logged", kind: "miss" },
  T: { activity: null, calories: "not_logged", kind: "miss" },
};

// Any dates do: the circles show a day number only on empty days and today.
const FIRST_DAY = "2026-10-12";

/** An example row's days, oldest first, and the day that counts as today (the "T", or the
    day after the row). Throws on a token it doesn't know, so a typo fails the tests. */
export function exampleDays(example: ExplainerExample): { days: StreakDay[]; today: string } {
  const days = example.days.map((token, index): StreakDay => {
    const look = TOKENS[token];
    if (!look) throw new Error(`Unknown day "${token}" in the streak explainer`);
    return {
      date: addDays(FIRST_DAY, index),
      weekday: "",
      state: example.expect.states[index] as DayState,
      kind: look.kind,
      recovery_logged: false,
      primary_activity_type: look.activity,
      calorie_status: look.calories,
    };
  });
  const last = example.days.length - 1;
  const today = example.days[last] === "T" ? days[last].date : addDays(days[last].date, 1);
  return { days, today };
}
