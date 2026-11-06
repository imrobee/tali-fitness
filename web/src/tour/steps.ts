// The tour's steps, read from steps.json so the words can change without touching code
// (UI_SPEC.md section 12). Checked here (shape), in src/copy.test.ts (spelling, names,
// em dashes) and in api/tests/test_tour_claims.py (the facts the words state).

import type { ExplainerExample } from "../lib/streakExplainer";
import data from "./steps.json";

export interface TourButton {
  label: string;
  does: "next" | "back" | "close" | "link";
  to?: string; // for "link"
}

export interface TourStep {
  id: string;
  route?: string; // may hold {placeholders}, like /activities?date={lift_day}; none: stay put
  placement: "modal" | "sheet";
  targets: string[]; // CSS selectors; one spotlight around all of them (none on a modal)
  within?: string; // the first element matching it holds the targets and the open selector
  open?: string; // a selector to click first (expands a session)
  legend?: "streak" | "calendar";
  title: string;
  body: string;
  technical?: string; // shown with Technical details on (sheet steps only)
  example?: ExplainerExample; // the streak explainer: a row of days drawn like the card
  note?: string; // the streak explainer: one quiet line under the body
  buttons?: TourButton[]; // the footer; Back and Next when not given
}

export const STEPS: TourStep[] = data.steps as TourStep[];

/** The values a step may quote: numbers from the demo's last rebuild, never live ones,
    and never the demo user's nickname. */
export const PLACEHOLDERS = [
  "streak_days",
  "best_streak",
  "eaten",
  "budget",
  "n_checks",
  "n_warnings",
  "n_quarantined",
  "lift_day",
] as const;

export type Story = Partial<Record<string, string | number | null>>;

function present(value: string | number | null | undefined): value is string | number {
  return value !== undefined && value !== null && value !== 0 && value !== "";
}

function show(value: string | number): string {
  return typeof value === "number" ? value.toLocaleString("en-US") : value;
}

/** Fills {placeholders} from the story. A sentence whose value is missing or zero is
    left out entirely, so the tour never says "a 0-day streak" or "… calories". Paragraphs
    (split by a blank line) are kept. */
export function fill(text: string, story: Story): string {
  return text
    .split("\n\n")
    .map((paragraph) => fillParagraph(paragraph, story))
    .filter(Boolean)
    .join("\n\n");
}

function fillParagraph(text: string, story: Story): string {
  const sentences = text.split(/(?<=[.!?])\s+/);
  const kept = sentences.filter((sentence) =>
    [...sentence.matchAll(/\{(\w+)\}/g)].every((match) => present(story[match[1]])),
  );
  return kept
    .join(" ")
    .replace(/\{(\w+)\}/g, (_, name: string) => show(story[name] as string | number));
}

export interface TextPart {
  text: string;
  italic: boolean;
}

/** A body's paragraphs (split by a blank line), each a list of parts; *words* in asterisks
    are italic. Nothing else is markup, so the words stay plain text in the data file. */
export function paragraphs(text: string): TextPart[][] {
  return text.split("\n\n").map((paragraph) =>
    paragraph
      .split(/(\*[^*]+\*)/)
      .filter(Boolean)
      .map((part) =>
        part.length > 2 && part.startsWith("*") && part.endsWith("*")
          ? { text: part.slice(1, -1), italic: true }
          : { text: part, italic: false },
      ),
  );
}

/** The step's page. Without the value a route needs, the page without its query. */
export function fillRoute(route: string, story: Story): string {
  const [path, query] = route.split("?");
  if (!query) return path;
  const names = [...query.matchAll(/\{(\w+)\}/g)].map((match) => match[1]);
  if (!names.every((name) => present(story[name]))) return path;
  return `${path}?${query.replace(/\{(\w+)\}/g, (_, name: string) => show(story[name] as string | number))}`;
}

export function counter(index: number, total: number): string {
  return `${index + 1} of ${total}`;
}

/** The footer for a step: its own buttons, or Back (after the first) and Next. */
export function footer(step: TourStep, index: number): TourButton[] {
  if (step.buttons) return step.buttons;
  const next: TourButton = { label: "Next", does: "next" };
  return index > 0 ? [{ label: "Back", does: "back" }, next] : [next];
}

/** The Technical details switch: only on the sheet steps that have technical words. */
export function hasSwitch(step: TourStep): boolean {
  return step.placement === "sheet" && Boolean(step.technical?.trim());
}

/** Problems with a list of steps (empty when it is valid). */
export function stepProblems(steps: TourStep[], routes: string[]): string[] {
  const problems: string[] = [];
  const ids = new Set<string>();
  if (steps.length < 6 || steps.length > 8) problems.push(`${steps.length} steps; the tour has 6 to 8`);
  steps.forEach((step, index) => {
    if (ids.has(step.id)) problems.push(`${step.id}: id used twice`);
    ids.add(step.id);
    if (!step.route || !routes.includes(step.route.split("?")[0])) {
      problems.push(`${step.id}: no page at ${step.route}`);
    }
    if (!step.title.trim() || !step.body.trim()) problems.push(`${step.id}: empty words`);
    if (step.placement === "modal" && (step.targets.length > 0 || step.technical)) {
      problems.push(`${step.id}: a modal has no spotlight and no technical details`);
    }
    if (step.placement === "sheet" && step.targets.length === 0) problems.push(`${step.id}: nothing to spotlight`);
    if (footer(step, index).length > 2) problems.push(`${step.id}: more than 2 buttons`);
    const words = [step.title, step.body, step.technical ?? "", step.route ?? ""].join(" ");
    for (const match of words.matchAll(/\{(\w+)\}/g)) {
      if (!(PLACEHOLDERS as readonly string[]).includes(match[1])) {
        problems.push(`${step.id}: unknown value {${match[1]}}`);
      }
    }
  });
  return problems;
}
