import { describe, expect, it } from "vitest";
import { counter, fill, fillRoute, footer, hasSwitch, PLACEHOLDERS, STEPS, stepProblems } from "./steps";

// The app's pages (App.tsx).
const ROUTES = ["/", "/activities", "/nutrition", "/me"];
// Every component's source, to find the data-tour names the steps point at.
const SOURCES = import.meta.glob("../**/*.tsx", { query: "?raw", import: "default", eager: true });
const TOUR_NAMES = new Set(
  Object.values(SOURCES).flatMap((source) =>
    [...String(source).matchAll(/(?:data-tour|tour|data-tour-part)="([a-z-]+)"/g)].map((match) => match[1]),
  ),
);

describe("the tour's steps (steps.json)", () => {
  it("are valid", () => {
    expect(stepProblems(STEPS, ROUTES)).toEqual([]);
  });

  it("each point at cards that exist", () => {
    const names = STEPS.flatMap((step) =>
      [...step.targets, step.within ?? "", step.open ?? ""].flatMap((selector) =>
        [...selector.matchAll(/data-tour(?:-part)?='([a-z-]+)'/g)].map((match) => match[1]),
      ),
    );

    expect(names.length).toBeGreaterThan(0);
    expect(names.filter((name) => !TOUR_NAMES.has(name))).toEqual([]);
  });

  it("start and end with a modal, and spotlight something in between", () => {
    expect(STEPS[0].placement).toBe("modal");
    expect(STEPS.at(-1)?.placement).toBe("modal");
    expect(STEPS.slice(1, -1).every((step) => step.placement === "sheet" && step.targets.length > 0)).toBe(true);
  });

  it("show calories and protein as one spotlight", () => {
    const calories = STEPS.find((step) => step.id === "calories");

    expect(calories?.targets).toEqual(["[data-tour='calories']", "[data-tour='protein']"]);
  });

  it("have the Technical details switch on steps 2 to 6 only", () => {
    expect(STEPS.map(hasSwitch)).toEqual([false, true, true, true, true, true, false]);
  });

  it("quote only values the demo's rebuild records, never the nickname", () => {
    const used = STEPS.flatMap((step) =>
      [...`${step.route} ${step.title} ${step.body} ${step.technical ?? ""}`.matchAll(/\{(\w+)\}/g)].map(
        (match) => match[1],
      ),
    );

    expect(used.length).toBeGreaterThan(0);
    expect(used.filter((name) => !(PLACEHOLDERS as readonly string[]).includes(name))).toEqual([]);
    expect(PLACEHOLDERS).not.toContain("nickname");
  });

  it("catch their own mistakes", () => {
    const broken = [
      { ...STEPS[0], route: "/nowhere" },
      STEPS[0],
      { ...STEPS[2], body: "Hello {nickname}." },
      ...STEPS.slice(3),
    ];

    expect(stepProblems(broken, ROUTES)).toEqual([
      "welcome: no page at /nowhere",
      "welcome: id used twice",
      "calories: unknown value {nickname}",
    ]);
  });
});

describe("fill", () => {
  it("quotes the story's number, with a thousands separator", () => {
    expect(fill("So far, {eaten} of the {budget} budget.", { eaten: 1068, budget: 1850 })).toBe(
      "So far, 1,068 of the 1,850 budget.",
    );
  });

  it("leaves out a sentence whose value is missing", () => {
    expect(fill("Each circle is a day. A {streak_days}-day streak.", {})).toBe("Each circle is a day.");
  });

  it("leaves out a sentence whose value is zero", () => {
    expect(fill("The ring. So far, {eaten} eaten. Tap it.", { eaten: 0 })).toBe("The ring. Tap it.");
  });
});

describe("fillRoute", () => {
  it("fills the date of the gym session", () => {
    expect(fillRoute("/activities?date={lift_day}", { lift_day: "2026-10-15" })).toBe(
      "/activities?date=2026-10-15",
    );
  });

  it("drops the query when it doesn't have the date", () => {
    expect(fillRoute("/activities?date={lift_day}", {})).toBe("/activities");
  });
});

describe("footer", () => {
  it("is Back and Next in the middle, and never more than two buttons", () => {
    expect(footer(STEPS[2], 2).map((button) => button.label)).toEqual(["Back", "Next"]);
    expect(STEPS.every((step, index) => footer(step, index).length <= 2)).toBe(true);
  });

  it("puts the main choice last (the primary button)", () => {
    expect(footer(STEPS[0], 0).map((button) => button.label)).toEqual(["Skip", "Show me around"]);
    expect(footer(STEPS[6], 6).map((button) => button.label)).toEqual(["How it works", "Explore the demo"]);
  });
});

it("counts steps from 1", () => {
  expect(counter(2, 7)).toBe("3 of 7");
});
