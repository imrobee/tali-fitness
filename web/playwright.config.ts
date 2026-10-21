import { defineConfig } from "@playwright/test";

// Screenshots of demo scenarios (UI_SPEC.md 11). Runs in the `screenshots` container
// against the demo web server; never against the real data.
export default defineConfig({
  testDir: "./e2e",
  reporter: "line",
  use: {
    baseURL: process.env.BASE_URL ?? "http://web-demo:5173",
    viewport: { width: 393, height: 852 }, // iPhone 15 / 16
    deviceScaleFactor: 2,
    colorScheme: "dark",
    reducedMotion: "reduce", // the ring is captured full, not mid-animation
  },
});
