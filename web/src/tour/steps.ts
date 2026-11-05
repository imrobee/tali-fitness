// The tour's steps, read from steps.json so the words can change without touching code
// (UI_SPEC.md section 12). Checked here (shape) and in api/tests/test_tour_lineage.py
// (every table, function, DAG, task and endpoint name exists).

import data from "./steps.json";

export type LineageKind = "source" | "endpoint" | "dag" | "task" | "table" | "function";
export type Placement = "top" | "bottom" | "center";

export interface TourStep {
  id: string;
  route: string;
  target: string | null; // a data-tour name on that page; null = no spotlight
  placement: Placement;
  title: string;
  text: string;
  built: string; // the "how it's built" line
  lineage: { kind: LineageKind; name: string }[];
}

export const STEPS: TourStep[] = data.steps as TourStep[];

/** Values a step's words may quote, read from what is on screen. */
export type TourValues = { streak?: number };

/** "{streak}" becomes the number on screen; an unknown value becomes "…". */
export function fill(text: string, values: TourValues): string {
  return text.replace(/\{(\w+)\}/g, (_, name: string) => {
    const value = values[name as keyof TourValues];
    return value === undefined ? "…" : String(value);
  });
}

export function counter(index: number, total: number): string {
  return `${index + 1} of ${total}`;
}

/** Problems with a list of steps (empty when it is valid). */
export function stepProblems(steps: TourStep[], routes: string[]): string[] {
  const problems: string[] = [];
  const kinds: LineageKind[] = ["source", "endpoint", "dag", "task", "table", "function"];
  const ids = new Set<string>();
  if (steps.length < 6 || steps.length > 8) problems.push(`${steps.length} steps; the tour has 6 to 8`);
  for (const step of steps) {
    if (ids.has(step.id)) problems.push(`${step.id}: id used twice`);
    ids.add(step.id);
    if (!routes.includes(step.route)) problems.push(`${step.id}: no page at ${step.route}`);
    if (!step.title.trim() || !step.text.trim() || !step.built.trim()) problems.push(`${step.id}: empty words`);
    if (!["top", "bottom", "center"].includes(step.placement)) problems.push(`${step.id}: placement`);
    if ((step.target === null) !== (step.placement === "center")) {
      problems.push(`${step.id}: only a step without a target is centred`);
    }
    for (const item of step.lineage) {
      if (!kinds.includes(item.kind)) problems.push(`${step.id}: lineage kind ${item.kind}`);
    }
  }
  return problems;
}
