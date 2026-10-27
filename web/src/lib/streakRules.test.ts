import { describe, expect, it } from "vitest";
import { chipText, periodText, streakRules, vacationError } from "./streakRules";

describe("how the streak works", () => {
  it("explains the rules in plain words, without internal names", () => {
    const text = streakRules(false).join(" ");

    expect(text).toContain("Two days over budget in a row end the streak.");
    expect(text).toContain("Two rest days in a row end the streak.");
    expect(text).toContain("A day with nothing logged ends the streak.");
    expect(text).not.toMatch(/\b(S|O|R|M)\b/);
  });

  it("follows the weekend setting", () => {
    expect(streakRules(true)).toContain("On weekends, only a day with nothing logged ends the streak.");
    expect(streakRules(false)).toContain("Weekends follow the same rules as weekdays.");
  });
});

describe("vacation form", () => {
  it("needs both dates in order", () => {
    expect(vacationError("", "2026-10-30")).toBe("Pick both dates.");
    expect(vacationError("2026-10-30", "2026-10-29")).toBe("From must be on or before To.");
    expect(vacationError("2026-10-29", "2026-10-29")).toBeNull();
  });

  it("names a period", () => {
    expect(periodText("2026-10-12", "2026-10-15")).toBe("Oct 12 – Oct 15");
    expect(periodText("2026-10-12", "2026-10-12")).toBe("Oct 12");
  });
});

describe("date chips", () => {
  it("invite a choice until a date is picked", () => {
    expect(chipText("")).toBe("Choose date");
    expect(chipText("2026-11-02")).toBe("Mon, Nov 2");
  });
});
