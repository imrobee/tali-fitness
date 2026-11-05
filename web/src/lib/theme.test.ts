import { describe, expect, it } from "vitest";
import { loadTheme, otherTheme, parseTheme, saveTheme, toggleLabel } from "./theme";

/** A Storage whose every call throws, like Safari with site data blocked. */
const blockedStorage = {
  getItem: () => {
    throw new Error("blocked");
  },
  setItem: () => {
    throw new Error("blocked");
  },
} as unknown as Storage;

describe("parseTheme", () => {
  it("is dark unless light was saved", () => {
    expect(parseTheme("light")).toBe("light");
    expect(parseTheme("dark")).toBe("dark");
    expect(parseTheme(null)).toBe("dark");
    expect(parseTheme("sepia")).toBe("dark");
  });
});

describe("otherTheme and toggleLabel", () => {
  it("names the theme a press switches to", () => {
    expect(otherTheme("dark")).toBe("light");
    expect(otherTheme("light")).toBe("dark");
    expect(toggleLabel("dark")).toBe("Switch to light mode");
    expect(toggleLabel("light")).toBe("Switch to dark mode");
  });
});

describe("loadTheme and saveTheme", () => {
  it("fall back to dark and do not throw when storage is blocked", () => {
    expect(loadTheme(blockedStorage)).toBe("dark");
    expect(() => saveTheme(blockedStorage, "light")).not.toThrow();
  });
});
