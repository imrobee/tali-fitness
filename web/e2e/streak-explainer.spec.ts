import { readFileSync } from "node:fs";
import { type Locator, type Page, expect, test } from "@playwright/test";
import { settled } from "./settle";

// The streak explainer (DECISIONS D129), walked in a real browser: opened from the "?" on
// the streak card, at phone size (375x812) and on desktop. On every step the streak card is
// fully on screen, not clipped and not covered by the sheet, and focus stays in the dialog;
// "Got it" gives focus back to the "?". Pictures: docs/screenshots/streak-help-<n>-<size>.png,
// and the Me page's card: streak-rules-me-<size>.png.

const EXPLAINER = JSON.parse(readFileSync("/app/streak/explainer.json", "utf8"));
const COUNT: number = EXPLAINER.items.length;
const scenario = process.env.SCENARIO ?? "midweek";
const SIZES = [
  { name: "375", width: 375, height: 812 },
  { name: "desktop", width: 1280, height: 800 },
];

for (const size of SIZES) {
  test(`the streak explainer at ${size.name}`, async ({ page }) => {
    test.skip(scenario !== "midweek", "the explainer runs on the main demo story");
    test.setTimeout(90_000);
    await page.setViewportSize({ width: size.width, height: size.height });
    // Not a first visit: the demo tour must not start by itself and cover the card.
    await page.addInitScript(() => localStorage.setItem("tali.tour-seen", "1"));
    expect((await page.request.post("/auth/demo")).status()).toBe(204);
    await page.goto("/");

    const help = page.getByRole("button", { name: "How streaks work" });
    await expect(help).toBeVisible();
    const helpBox = await help.boundingBox();
    expect(helpBox && Math.min(helpBox.width, helpBox.height)).toBeGreaterThanOrEqual(44);
    await help.click();

    const card = page.locator("[data-tour='streak']");
    const dialog = page.getByRole("dialog");
    for (let index = 0; index < COUNT; index += 1) {
      const item = EXPLAINER.items[index];
      await expect(dialog.getByText(`How your streak works · ${index + 1} of ${COUNT}`)).toBeVisible();
      await expect(dialog.getByRole("heading", { name: item.title })).toBeVisible();
      await expect(dialog.getByText(item.example.caption)).toBeVisible();
      await settled(page, card); // the scroll to the card has finished
      await checkCard(page, card, dialog, size.height);
      // Focus is inside the dialog (it takes focus on each step).
      expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true);
      await page.screenshot({ path: `screenshots/streak-help-${index + 1}-${size.name}.png` });
      if (index < COUNT - 1) await dialog.getByRole("button", { name: "Next" }).click();
    }

    await dialog.getByRole("button", { name: EXPLAINER.done }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(help).toBeFocused();

    // The Me page's card: the same six items, numbered.
    await page.goto("/me");
    const rules = page.getByRole("region", { name: EXPLAINER.title }).or(
      page.locator("section", { has: page.getByRole("heading", { name: EXPLAINER.title }) }),
    );
    await expect(rules.first().getByRole("listitem")).toHaveCount(COUNT);
    // For the picture only: the fixed bottom nav would be painted across the card.
    await page.addStyleTag({ content: 'nav[aria-label="Primary"] { display: none; }' });
    await rules.first().screenshot({ path: `screenshots/streak-rules-me-${size.name}.png` });
  });
}

async function checkCard(page: Page, card: Locator, dialog: Locator, viewportHeight: number) {
  const box = await card.boundingBox();
  const sheet = await dialog.boundingBox();
  expect(box, "the streak card is on the page").not.toBeNull();
  expect(sheet, "the sheet is on the page").not.toBeNull();
  if (!box || !sheet) return;
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(viewportHeight);
  const apart =
    box.x + box.width <= sheet.x ||
    sheet.x + sheet.width <= box.x ||
    box.y + box.height <= sheet.y ||
    sheet.y + sheet.height <= box.y;
  expect(apart, "the sheet covers the streak card").toBe(true);
  expect(await card.evaluate((element) => element.scrollWidth > element.clientWidth + 1)).toBe(false);
  // The sheet holds its words: on screen, and nothing inside spills out or scrolls.
  const problem = await dialog.evaluate((element) => {
    const outer = element.getBoundingClientRect();
    if (outer.top < -1 || outer.bottom > window.innerHeight + 1) return "the sheet is off screen";
    for (const node of element.querySelectorAll<HTMLElement>("*")) {
      if (node.getBoundingClientRect().bottom > outer.bottom + 1) return `spills: ${node.textContent?.slice(0, 40)}`;
    }
    return null;
  });
  expect(problem).toBeNull();
}
