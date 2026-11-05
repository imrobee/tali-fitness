import { describe, expect, it } from "vitest";
import { EXPLAINER, exampleDays, targetsLine } from "./streakExplainer";
import { circleLook, ringTone } from "./streakRing";

describe("the streak explainer's examples", () => {
  it("give a state for every day shown", () => {
    for (const item of EXPLAINER.items) {
      expect(item.example.expect.states).toHaveLength(item.example.days.length);
    }
  });

  it("draw each kind of day the way the streak card does", () => {
    const { days, today } = exampleDays({
      days: ["S", "O", "R", "A", "M", "T"],
      caption: "",
      expect: { states: ["counted", "counted", "counted", "counted", "at_risk", "pending"], streak: 4 },
    });
    const looks = days.map((day) => [circleLook(day, today), ringTone(day.calorie_status)]);

    expect(looks).toEqual([
      ["active", "green"], // a workout, within budget
      ["active", "orange"], // a workout, over budget
      ["recovery", "green"], // food within budget, no workout: the snowflake
      ["active", "grey"], // a workout, no food: a rest day, drawn as the card draws it
      ["at_risk", "grey"], // yesterday empty, still fixable
      ["today", "grey"],
    ]);
    expect(today).toBe(days[5].date);
  });

  it("treat the day after a row as today when the row has no T", () => {
    const { days, today } = exampleDays(EXPLAINER.items[0].example);

    expect(today > days[days.length - 1].date).toBe(true);
  });

  it("refuse a day they don't know, so a typo fails here", () => {
    expect(() => exampleDays({ days: ["X"], caption: "", expect: { states: ["counted"], streak: 1 } })).toThrow(
      /Unknown day "X"/,
    );
  });
});

describe("the explainer", () => {
  it("has six rules, each with an example", () => {
    expect(EXPLAINER.items.map((item) => item.title)).toEqual([
      "A full day",
      "Going over budget",
      "Rest days",
      "Nothing logged",
      "Breaks and weekends",
      "Timing",
    ]);
  });

  it("says how targets work in each mode", () => {
    expect(targetsLine(false)).toMatch(/past days keep the budget they had/);
    expect(targetsLine(true)).toMatch(/applies to every day/);
  });
});
