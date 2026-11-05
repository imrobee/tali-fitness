import { describe, expect, it } from "vitest";
import { counter, fill, STEPS, stepProblems } from "./steps";

// The app's pages (App.tsx).
const ROUTES = ["/", "/activities", "/nutrition", "/me"];
// Every component's source, to find the data-tour names the steps point at.
const SOURCES = import.meta.glob("../**/*.tsx", { query: "?raw", import: "default", eager: true });
const TOUR_NAMES = new Set(
  Object.values(SOURCES).flatMap((source) =>
    [...String(source).matchAll(/(?:data-tour|tour)="([a-z-]+)"/g)].map((match) => match[1]),
  ),
);

describe("the tour's steps (steps.json)", () => {
  it("are valid", () => {
    expect(stepProblems(STEPS, ROUTES)).toEqual([]);
  });

  it("each point at a card that exists", () => {
    const targets = STEPS.flatMap((step) => (step.target ? [step.target] : []));

    expect(targets.filter((target) => !TOUR_NAMES.has(target))).toEqual([]);
  });

  it("name where each piece of data comes from, except the last", () => {
    expect(STEPS.slice(0, -1).every((step) => step.lineage.length > 0)).toBe(true);
  });

  it("catch their own mistakes", () => {
    const broken = [{ ...STEPS[0], route: "/nowhere" }, STEPS[0], ...STEPS.slice(2)];

    expect(stepProblems(broken, ROUTES)).toEqual([
      "welcome: no page at /nowhere",
      "welcome: id used twice",
    ]);
  });
});

describe("fill", () => {
  it("quotes the streak on screen", () => {
    expect(fill("A {streak}-day streak", { streak: 12 })).toBe("A 12-day streak");
  });

  it("shows an ellipsis for a value not loaded yet", () => {
    expect(fill("A {streak}-day streak", {})).toBe("A …-day streak");
  });
});

it("counts steps from 1", () => {
  expect(counter(2, 7)).toBe("3 of 7");
});
