import { writeFile } from "node:fs/promises";
import { type Page, expect, test } from "@playwright/test";

// One scenario per run: `make screenshots` seeds the demo database with SCENARIO and runs
// this file. Every scenario gets its dashboard at iPhone and desktop size (UI_SPEC.md 11);
// midweek also gets the Activities (with a session open), Nutrition and Me pages.
const scenario = process.env.SCENARIO ?? "midweek";
const apiKey = process.env.API_KEY ?? "demo-key";
const OUT = "screenshots";

const VIEWPORTS = [
  { name: "iphone", width: 393, height: 852 },
  { name: "desktop", width: 1280, height: 800 },
];

test(`screenshots: ${scenario}`, async ({ page }) => {
  await page.addInitScript((key) => {
    window.localStorage.setItem("fitness-tracker.api-key", key);
  }, apiKey);

  for (const viewport of VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });

    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: /^Good / })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Calorie budget", exact: true })).toBeVisible();
    // Optional: save the rendered page for the design-taste inspector, which cannot get past
    // the key gate on its own. Written once, at the iPhone size.
    if (process.env.SNAPSHOT_DIR && viewport.name === "iphone") {
      await writeFile(`${process.env.SNAPSHOT_DIR}/${scenario}.html`, await page.content());
    }
    await capture(page, `${scenario}-${viewport.name}.png`);

    if (scenario === "midweek") {
      // Activities filtered to Saturday from the calendar, with the trend above it.
      await page.goto("/activities?date=2026-10-17");
      await expect(page.getByRole("heading", { level: 1, name: "Activities" })).toBeVisible();
      await expect(page.getByText(/^Last week: /)).toBeVisible();
      await expect(page.getByRole("heading", { name: "October 2026" })).toBeVisible();
      await page.getByRole("button", { name: /Full Body/ }).click();
      await expect(page.getByText("20 kg × 8")).toBeVisible();
      await capture(page, `midweek-activities-${viewport.name}.png`);

      await page.goto("/nutrition?date=2026-10-17");
      await expect(page.getByRole("heading", { name: "Weekly calorie budget" })).toBeVisible();
      await expect(page.getByText(/^7-day average: /)).toBeVisible();
      await capture(page, `midweek-nutrition-${viewport.name}.png`);

      // The same trends by month, at phone size only.
      if (viewport.name === "iphone") {
        await page.getByRole("group", { name: "Calorie trend range" }).getByRole("button", { name: "Month" }).click();
        await expect(page.getByText(/^Last month: /)).toBeVisible();
        await page.goto("/activities");
        await page.getByRole("group", { name: "Training trend range" }).getByRole("button", { name: "Month" }).click();
        await expect(page.getByText(/^Last month: /)).toBeVisible();
        await capture(page, "midweek-activities-month-iphone.png");
      }
    }

    // The Me page twice: a healthy pipeline (midweek) and a stale/failed one (at_risk).
    if (scenario === "midweek" || scenario === "at_risk") {
      await page.goto("/me");
      await expect(page.getByRole("heading", { name: "Data and sync" })).toBeVisible();
      await capture(page, `${scenario}-me-${viewport.name}.png`);
    }
  }
});

async function capture(page: Page, file: string) {
  // A full-page capture paints the fixed bottom nav where the first screen ends, over the
  // cards. For the picture only, let the nav follow the content (the page already reserves
  // its height); on a phone it stays fixed at the bottom.
  await page.addStyleTag({ content: 'nav[aria-label="Primary"] { position: static; }' });
  await page.screenshot({ path: `${OUT}/${file}`, fullPage: true });
}
