import { describe, expect, it } from "vitest";
import page from "./pages/howItWorks.json";
import tour from "./tour/steps.json";

// The words a first-time visitor reads (the tour, and the How it works page): plain US
// English, the app's full name, no em dashes, no hype, and no person's name. The demo
// user's nickname is checked against the scenario in api/tests/test_tour_claims.py.

const PAGE_SOURCE = import.meta.glob("./pages/HowItWorksPage.tsx", { query: "?raw", import: "default", eager: true });

/** Every string in a JSON file except its "_readme" note to the editor. */
function strings(value: unknown, where: string): { where: string; text: string }[] {
  if (typeof value === "string") return [{ where, text: value }];
  if (Array.isArray(value)) return value.flatMap((item) => strings(item, where));
  if (value && typeof value === "object") {
    return Object.entries(value)
      .filter(([key]) => key !== "_readme" && key !== "href")
      .flatMap(([key, item]) => strings(item, `${where} ${key}`));
  }
  return [];
}

/** Every string a visitor can read: the tour's words, and the page's text in JSX. */
function visibleCopy(): { where: string; text: string }[] {
  const steps = tour.steps.flatMap((step) =>
    [step.title, step.body, "technical" in step ? String(step.technical) : ""].map((text) => ({
      where: `tour ${step.id}`,
      text,
    })),
  );
  const pages = Object.entries(PAGE_SOURCE).flatMap(([where, source]) =>
    // Text between tags, and quoted strings: enough to catch a stray word.
    [...String(source).matchAll(/>([^<>{}]+)</g), ...String(source).matchAll(/"([^"\n]{12,})"/g)].map(
      (match) => ({ where, text: match[1] }),
    ),
  );
  return [...steps, ...strings(page, "howItWorks.json"), ...pages].filter((item) => item.text.trim());
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
