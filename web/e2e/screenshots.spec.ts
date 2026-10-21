import { writeFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

// One scenario per run: `make screenshots` seeds the demo database with SCENARIO and
// runs this file, which saves the iPhone-size dashboard into docs/screenshots/.
const scenario = process.env.SCENARIO ?? "midweek";
const apiKey = process.env.API_KEY ?? "demo-key";

test(`dashboard: ${scenario}`, async ({ page }) => {
  await page.addInitScript((key) => {
    window.localStorage.setItem("fitness-tracker.api-key", key);
  }, apiKey);

  await page.goto("/");
  // The greeting h1 appears only once the dashboard data has loaded.
  await expect(page.getByRole("heading", { level: 1, name: /^Good / })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Calorie budget" })).toBeVisible();

  // Optional: save the rendered page (Vite's dev styles are inline <style> tags) for
  // the design-taste inspector, which cannot get past the key gate on its own.
  if (process.env.SNAPSHOT_DIR) {
    await writeFile(`${process.env.SNAPSHOT_DIR}/${scenario}.html`, await page.content());
  }

  // A full-page capture paints the fixed bottom nav where the first screen ends, over
  // the cards. For the picture only, let the nav follow the content (the page already
  // reserves its height); on a phone it stays fixed at the bottom.
  await page.addStyleTag({ content: 'nav[aria-label="Primary"] { position: static; }' });
  await page.screenshot({ path: `screenshots/${scenario}-iphone.png`, fullPage: true });
});
