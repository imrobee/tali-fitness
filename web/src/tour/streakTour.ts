// The streak explainer as tour steps (DECISIONS D129): the same sheet and spotlight as the
// demo tour, pointed at the streak card, with a row of example days under each rule.

import { EXPLAINER, targetsLine } from "../lib/streakExplainer";
import type { TourStep } from "./steps";

/** One step per rule, all on the streak card; the last says "Got it" and carries the line
    about targets for this mode. No route: it opens on the dashboard, where the card is. */
export function streakSteps(demo: boolean): TourStep[] {
  const last = EXPLAINER.items.length - 1;
  return EXPLAINER.items.map((item, index) => ({
    id: item.id,
    placement: "sheet",
    targets: ["[data-tour='streak']"],
    title: item.title,
    body: item.body,
    example: item.example,
    note: index === last ? targetsLine(demo) : undefined,
    buttons:
      index === last
        ? [
            { label: "Back", does: "back" },
            { label: EXPLAINER.done, does: "close" },
          ]
        : undefined,
  }));
}
