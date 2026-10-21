import { describe, expect, it } from "vitest";
import { clockTime, reasonLabel, sourceName, statusLabel, timeAgo } from "./pipeline";

const NOW = Date.parse("2026-10-20T12:00:00Z");
const hoursAgo = (hours: number) => new Date(NOW - hours * 3_600_000).toISOString();

describe("timeAgo", () => {
  it.each([
    [0, "just now"],
    [0.5, "30 min ago"],
    [1, "1 hour ago"],
    [9, "9 hours ago"],
    [47, "47 hours ago"],
    [49, "2 days ago"],
    [24 * 10, "10 days ago"],
  ])("%s hours ago reads as %s", (hours, text) => {
    expect(timeAgo(hoursAgo(hours), NOW)).toBe(text);
  });
});

describe("statusLabel and sourceName", () => {
  it("gives the text that goes with each status icon", () => {
    expect([statusLabel("ok"), statusLabel("delayed"), statusLabel("failed")]).toEqual([
      "OK",
      "Delayed",
      "Failed",
    ]);
  });

  it("names the sources as the user knows them", () => {
    expect(sourceName("strava")).toBe("Strava");
    expect(sourceName("health")).toBe("Apple Health");
    expect(sourceName("other")).toBe("other");
  });
});

describe("clockTime", () => {
  it("shows the time in Asia/Manila, not the browser's zone", () => {
    // 07:04 UTC on Tuesday is 15:04 in Manila (UTC+8).
    expect(clockTime("2026-10-20T07:04:00Z")).toBe("Tue 15:04");
  });
});

describe("reasonLabel", () => {
  it("translates known reasons and passes unknown ones through", () => {
    expect(reasonLabel("unparsed_line")).toBe("Line not understood");
    expect(reasonLabel("new_reason")).toBe("new_reason");
  });
});
