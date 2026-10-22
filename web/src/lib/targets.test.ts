import { describe, expect, it } from "vitest";
import { validateProfile } from "./targets";

const valid = { nickname: "Rob", calorieBudget: "1853", proteinGoal: "130", weightGoal: "", weightUnit: "kg" as const };

describe("validateProfile", () => {
  it("accepts targets inside the limits", () => {
    expect(validateProfile(valid)).toEqual({});
    expect(validateProfile({ ...valid, calorieBudget: "800", proteinGoal: "0" })).toEqual({});
  });

  it("accepts a nickname-only save that leaves targets empty", () => {
    expect(validateProfile({ nickname: "Rob", calorieBudget: "", proteinGoal: "", weightGoal: "", weightUnit: "kg" })).toEqual({});
  });

  it.each([
    [{ calorieBudget: "799" }, "calorieBudget"],
    [{ calorieBudget: "6001" }, "calorieBudget"],
    [{ calorieBudget: "1853.5" }, "calorieBudget"],
    [{ proteinGoal: "401" }, "proteinGoal"],
    [{ proteinGoal: "" }, "proteinGoal"], // both targets go together
    [{ nickname: "x".repeat(41) }, "nickname"],
  ])("rejects %o", (change, field) => {
    expect(Object.keys(validateProfile({ ...valid, ...change }))).toEqual([field]);
  });
});

describe("weight goal", () => {
  it("accepts a weight with at most one decimal, or nothing", () => {
    expect(validateProfile({ ...valid, weightGoal: "72.5" })).toEqual({});
    expect(validateProfile({ ...valid, weightGoal: "" })).toEqual({});
  });

  it("refuses values outside 30-250 kg or with two decimals", () => {
    for (const weightGoal of ["5", "300", "72.55", "abc"]) {
      expect(Object.keys(validateProfile({ ...valid, weightGoal }))).toEqual(["weightGoal"]);
    }
  });
});

describe("weight goal in pounds", () => {
  it("uses pound limits that match 30-250 kg", () => {
    expect(validateProfile({ ...valid, weightUnit: "lb", weightGoal: "160" })).toEqual({});
    expect(Object.keys(validateProfile({ ...valid, weightUnit: "lb", weightGoal: "40" }))).toEqual([
      "weightGoal",
    ]);
  });
});
