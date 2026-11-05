import { describe, expect, it } from "vitest";
import tour from "./tour/steps.json";

// The words a first-time visitor reads (the tour, and the How it works page): plain US
// English, the app's full name, no em dashes, no hype, and no person's name. The demo
// user's nickname is checked against the scenario in api/tests/test_tour_claims.py.

const PAGES = import.meta.glob("./pages/HowItWorksPage.tsx", { query: "?raw", import: "default", eager: true });

/** Every string a visitor can read: the tour's words, and the page's text in JSX. */
function visibleCopy(): { where: string; text: string }[] {
  const steps = tour.steps.flatMap((step) =>
    [step.title, step.body, "technical" in step ? String(step.technical) : ""].map((text) => ({
      where: `tour ${step.id}`,
      text,
    })),
  );
  const pages = Object.entries(PAGES).flatMap(([where, source]) =>
    // Text between tags, and quoted strings: enough to catch a stray word.
    [...String(source).matchAll(/>([^<>{}]+)</g), ...String(source).matchAll(/"([^"\n]{12,})"/g)].map(
      (match) => ({ where, text: match[1] }),
    ),
  );
  return [...steps, ...pages].filter((item) => item.text.trim());
}

const NAMES = /\b(Rob|Robee|Feliciano|Taiki)\b/;
const HYPE = /\b(seamless(ly)?|robust|leverag\w*|powerful)\b/i;
const BRITISH =
  /\b(colour\w*|favourite\w*|organis\w*|recognis\w*|behaviour\w*|centre\w*|analys(e|ed|ing)|optimis\w*|summaris\w*|licence|catalogue|programme)\b/i;

describe("visitor-facing copy", () => {
  const copy = visibleCopy();

  it("finds the words to check", () => {
    expect(copy.length).toBeGreaterThan(20);
  });

  it.each([
    ["an em dash", /—/],
    ["a person's name", NAMES],
    ["a hype word", HYPE],
    ["British spelling", BRITISH],
    ["the app's name without Fitness", /\bTali\b(?! Fitness)/],
  ])("has no %s", (_, pattern) => {
    expect(copy.filter((item) => pattern.test(item.text))).toEqual([]);
  });
});
