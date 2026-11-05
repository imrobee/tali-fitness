import { readFileSync } from "node:fs";
import { type Locator, type Page, expect, test } from "@playwright/test";

// The demo tour, walked in a real browser (UI_SPEC.md section 12): at phone size
// (375x812, a bottom sheet) and on desktop, with Technical details off and on. On every
// step with a spotlight: its cards are fully on screen, not clipped, not covered by the
// tour's dialog, and show data, not an empty state; the dialog never scrolls inside.
// Pictures go to docs/screenshots/tour-<step>-<size>[-tech].png.

type Step = {
  id: string;
  placement: "modal" | "sheet";
  targets: string[];
  within?: string;
  open?: string;
  technical?: string;
  buttons?: { label: string; does: string }[];
};
const STEPS: Step[] = JSON.parse(readFileSync("/app/tour/steps.json", "utf8")).steps;
const scenario = process.env.SCENARIO ?? "midweek";
const EMPTY_STATES = [/No exercises logged/, /Set your calorie budget/, /Records appear once/];
const SIZES = [
  { name: "375", width: 375, height: 812 },
  { name: "desktop", width: 1280, height: 800 },
];

for (const size of SIZES) {
  for (const technical of [false, true]) {
    test(`the tour at ${size.name}, technical details ${technical ? "on" : "off"}`, async ({ page }) => {
      test.skip(scenario !== "midweek", "the tour runs on the main demo story");
      test.setTimeout(120_000);
      await page.setViewportSize({ width: size.width, height: size.height });
      if (technical) await page.addInitScript(() => sessionStorage.setItem("tali.tour-details", "1"));
      expect((await page.request.post("/auth/demo")).status()).toBe(204);
      await page.goto("/"); // a first visit: the tour starts by itself
      const suffix = technical ? `${size.name}-tech` : size.name;

      for (const [index, step] of STEPS.entries()) {
        const dialog = page.getByRole("dialog");
        await expect(dialog.getByText(`${index + 1} of ${STEPS.length}`)).toBeVisible();
        await expect(dialog.getByRole("switch")).toHaveCount(step.placement === "sheet" ? 1 : 0);
        if (step.placement === "sheet") {
          const scope = step.within ? page.locator(step.within).first() : page.locator(":root");
          const targets = scope.locator(step.targets.join(", "));
          await expect(targets.first()).toBeVisible();
          await page.waitForTimeout(700); // the scroll to the card settles
          if (step.open) {
            // A step that opens something (the gym session) must show it open.
            await expect(page.locator("[data-tour='strength-session'] [aria-expanded='true']")).toHaveCount(1);
            await page.waitForTimeout(600); // the sets arrive and the card settles
          }
          await checkStep(page, targets, dialog, size.height);
          const technicalWords = dialog.getByText(step.technical?.slice(0, 30) ?? "");
          const more = dialog.getByRole("button", { name: /^Show (more|technical details)$/ });
          if (await more.count()) {
            await page.screenshot({ path: `screenshots/tour-${step.id}-${suffix}.png` });
            await more.click();
            await page.waitForTimeout(300);
            await expect(technicalWords).toBeVisible(); // all of it, in place of the body
            await checkStep(page, targets, dialog, size.height);
            await page.screenshot({ path: `screenshots/tour-${step.id}-${suffix}-more.png` });
            await dialog.getByRole("button", { name: "Show less" }).click();
          } else {
            if (technical) await expect(technicalWords).toBeVisible();
            await page.screenshot({ path: `screenshots/tour-${step.id}-${suffix}.png` });
          }
        } else {
          await checkDialog(dialog);
          await page.screenshot({ path: `screenshots/tour-${step.id}-${suffix}.png` });
        }
        await advance(dialog, step, index);
      }
      await expect(page.getByRole("dialog")).toHaveCount(0);
    });
  }
}

/** The words fit the dialog: it is on screen, nothing inside spills past its edges, and
    nothing in it scrolls (a clamped paragraph, with Show more, is the one allowed cut). */
async function checkDialog(dialog: Locator) {
  const problem = await dialog.evaluate((element) => {
    const box = element.getBoundingClientRect();
    if (box.top < -1 || box.bottom > window.innerHeight + 1) return "the dialog is off screen";
    for (const node of element.querySelectorAll<HTMLElement>("*")) {
      const inner = node.getBoundingClientRect();
      if (inner.bottom > box.bottom + 1) return `spills out: ${node.textContent?.slice(0, 40)}`;
      const scrolls = getComputedStyle(node).overflowY;
      if ((scrolls === "auto" || scrolls === "scroll") && node.scrollHeight > node.clientHeight + 1) {
        return `scrolls: ${node.textContent?.slice(0, 40)}`;
      }
    }
    return null;
  });
  expect(problem).toBeNull();
}

async function checkStep(page: Page, targets: Locator, dialog: Locator, viewportHeight: number) {
  const boxes = (await targets.evaluateAll((elements) =>
    elements.map((element) => {
      const r = element.getBoundingClientRect();
      return { x: r.left, y: r.top, width: r.width, height: r.height };
    }),
  )) as { x: number; y: number; width: number; height: number }[];
  const sheet = await dialog.boundingBox();
  expect(boxes.length, "the cards are on the page").toBeGreaterThan(0);
  expect(sheet, "the dialog is on the page").not.toBeNull();
  if (!sheet) return;
  const top = Math.min(...boxes.map((b) => b.y));
  const bottom = Math.max(...boxes.map((b) => b.y + b.height));
  const left = Math.min(...boxes.map((b) => b.x));
  const right = Math.max(...boxes.map((b) => b.x + b.width));
  const box = { x: left, y: top, width: right - left, height: bottom - top };

  // Fully on screen, top to bottom.
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(viewportHeight);
  // Not covered by the dialog: the two boxes do not overlap.
  const apart =
    box.x + box.width <= sheet.x ||
    sheet.x + sheet.width <= box.x ||
    box.y + box.height <= sheet.y ||
    sheet.y + sheet.height <= box.y;
  expect(apart, "the dialog covers the card").toBe(true);
  // Not clipped inside: nothing spills past its own edges.
  const clipped = await targets.evaluateAll((elements) =>
    elements.some((element) => element.scrollWidth > element.clientWidth + 1),
  );
  expect(clipped, "the card is clipped").toBe(false);
  // Data, not an empty state.
  const words = (await targets.allInnerTexts()).join("\n");
  for (const empty of EMPTY_STATES) expect(words).not.toMatch(empty);
  await expect(page.locator("[data-tour] [data-loading]")).toHaveCount(0);
  await checkDialog(dialog);
}

async function advance(dialog: Locator, step: Step, index: number) {
  if (index === STEPS.length - 1) {
    await dialog.getByRole("button", { name: "Explore the demo" }).click();
  } else if (step.buttons) {
    await dialog.getByRole("button", { name: step.buttons.at(-1)?.label }).click();
  } else {
    await dialog.getByRole("button", { name: "Next" }).click();
  }
}
