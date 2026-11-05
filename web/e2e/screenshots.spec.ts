import { writeFile } from "node:fs/promises";
import { type Page, expect, test } from "@playwright/test";

// One scenario per run: `make screenshots` seeds the demo database with SCENARIO and runs
// this file. Every scenario gets its dashboard at iPhone and desktop size (UI_SPEC.md 11);
// midweek also gets the Activities (with a session open), Nutrition and Me pages.
const scenario = process.env.SCENARIO ?? "midweek";
const OUT = "screenshots";

const VIEWPORTS = [
  { name: "iphone", width: 393, height: 852 },
  { name: "desktop", width: 1280, height: 800 },
];

test(`screenshots: ${scenario}`, async ({ page }) => {
  // midweek captures about twenty pages (both sizes plus the light theme): around 20s on a
  // warm dev server, so the default 30s limit failed it now and then.
  test.setTimeout(90_000);

  // The launch screen, before the visit starts. The demo service has no launch screen (it
  // starts a visit by itself), so the method is faked as Google to picture the real one.
  if (scenario === "midweek") {
    await page.route("**/auth/method", (route) => route.fulfill({ json: { method: "google" } }));
    for (const viewport of VIEWPORTS) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto("/");
      await expect(page.getByRole("link", { name: "Sign in with Google" })).toBeVisible();
      await page.screenshot({ path: `${OUT}/launch-${viewport.name}.png` });
    }
    await page.setViewportSize({ width: 393, height: 852 });
    await page.evaluate(() => localStorage.setItem("fitness-tracker.theme", "light"));
    await page.reload();
    await expect(page.getByRole("button", { name: "Demo version" })).toBeVisible();
    await page.screenshot({ path: `${OUT}/launch-light-iphone.png` });
    await page.evaluate(() => localStorage.removeItem("fitness-tracker.theme"));
    await page.unroute("**/auth/method");
  }

  // Start a demo visit, as opening the demo does. page.request shares the page's cookies,
  // so the demo cookie it gets back opens the pages too.
  const visit = await page.request.post("/auth/demo");
  expect(visit.status()).toBe(204);

  for (const viewport of VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });

    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: /^Good / })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Calorie budget", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Calories by day" })).toBeVisible();
    // Optional: save the rendered page for the design-taste inspector, which cannot get past
    // the key gate on its own. Written once, at the iPhone size.
    if (process.env.SNAPSHOT_DIR && viewport.name === "iphone") {
      await writeFile(`${process.env.SNAPSHOT_DIR}/${scenario}.html`, await page.content());
    }
    await capture(page, `${scenario}-${viewport.name}.png`);

    if (scenario === "midweek") {
      // Activities filtered to Saturday from the calendar, which leads the page.
      await page.goto("/activities?date=2026-10-17");
      await expect(page.getByRole("heading", { level: 1, name: "Activities" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "October 2026" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Personal records" })).toBeVisible();
      await page.getByRole("button", { name: /Full Body/ }).click();
      await expect(page.getByText("20 kg × 8")).toBeVisible();
      await capture(page, `midweek-activities-${viewport.name}.png`);

      await page.goto("/nutrition?date=2026-10-17");
      await expect(page.getByRole("heading", { name: "Calories by day" })).toBeVisible();
      await expect(page.getByText(/^7-day average: [\d,]+ kcal/)).toBeVisible();
      await expect(page.getByRole("heading", { name: "Weight" })).toBeVisible();
      await capture(page, `midweek-nutrition-${viewport.name}.png`);

      // The calorie trend by month, at phone size only.
      if (viewport.name === "iphone") {
        await page.getByRole("group", { name: "Calorie trend range" }).getByRole("button", { name: "Month" }).click();
        await expect(page.getByRole("group", { name: "Calorie trend range" }).getByRole("button", { name: "Month" })).toHaveAttribute("aria-pressed", "true");
        await capture(page, "midweek-nutrition-month-iphone.png");

        // Pounds. The demo is read-only, so the saved unit can't change: the test rewrites
        // the profile the API sends instead, and every weight on the page follows it.
        await page.route("**/api/v1/me", async (route) => {
          const response = await route.fetch();
          await route.fulfill({ response, json: { ...(await response.json()), weight_unit: "lb" } });
        });
        await page.goto("/nutrition?date=2026-10-17");
        await expect(page.getByText(/^Last weigh-in: [\d.]+ lb$/)).toBeVisible();
        await capture(page, "midweek-nutrition-lb-iphone.png");
        await page.unroute("**/api/v1/me");
      }
    }

    // The Me page twice: a healthy pipeline (midweek) and a stale/failed one (at_risk).
    if (scenario === "midweek" || scenario === "at_risk") {
      await page.goto("/me");
      await expect(page.getByRole("heading", { name: "Data and sync" })).toBeVisible();
      await capture(page, `${scenario}-me-${viewport.name}.png`);
    }
  }

  // The light theme, at phone size: switched with the header toggle, kept across a reload.
  if (scenario === "midweek") {
    await page.setViewportSize({ width: 393, height: 852 });
    await page.goto("/");
    await page.getByRole("button", { name: "Switch to light mode" }).click();
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expect(page.getByRole("heading", { name: "Calories by day" })).toBeVisible();
    await capture(page, "midweek-light-iphone.png");
    // Each card loads its own data, so wait for the last card on the page, not just the title.
    for (const [path, name, lastCard] of [
      ["/activities?date=2026-10-17", "activities", "Personal records"],
      ["/nutrition?date=2026-10-17", "nutrition", "Weight"],
      ["/me", "me", "Data and sync"],
    ]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: lastCard, exact: true })).toBeVisible();
      await capture(page, `midweek-${name}-light-iphone.png`);
    }
    await page.getByRole("button", { name: "Switch to dark mode" }).click();
  }
});

async function capture(page: Page, file: string) {
  // A full-page capture paints the fixed bottom nav where the first screen ends, over the
  // cards. For the picture only, let the nav follow the content (the page already reserves
  // its height); on a phone it stays fixed at the bottom.
  await page.addStyleTag({ content: 'nav[aria-label="Primary"] { position: static; }' });
  await page.screenshot({ path: `${OUT}/${file}`, fullPage: true });
}
