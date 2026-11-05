import type { Locator, Page } from "@playwright/test";

/** Waits until the page has stopped scrolling and these elements have stopped moving: the
    same box twice, 150 ms apart (at most 8 s). A fixed wait was too short when every browser
    test ran at once and the smooth scroll took longer. */
export async function settled(page: Page, targets: Locator): Promise<void> {
  let last = "";
  for (let tries = 0; tries < 50; tries += 1) {
    const now = JSON.stringify([
      await page.evaluate(() => window.scrollY),
      await targets.evaluateAll((elements) => elements.map((element) => element.getBoundingClientRect().toJSON())),
    ]);
    if (now === last) return;
    last = now;
    await page.waitForTimeout(150);
  }
}
