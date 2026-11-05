import { describe, expect, it } from "vitest";
import { chipText, periodText, showRecoveryCard, vacationError, weekendRule } from "./streakRules";

describe("the weekend rule", () => {
  it("follows the setting", () => {
    expect(weekendRule(true)).toBe("On weekends, only a day with nothing logged ends the streak.");
    expect(weekendRule(false)).toBe("Weekends follow the same rules as weekdays.");
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

describe("the dashboard's recovery card", () => {
  it("hides on a day with an activity, unless a recovery day was logged", () => {
    expect(showRecoveryCard(0, "available")).toBe(true);
    expect(showRecoveryCard(1, "counted")).toBe(false);
    expect(showRecoveryCard(2, "available")).toBe(false);
    expect(showRecoveryCard(1, "logged")).toBe(true); // still undoable
  });
});
