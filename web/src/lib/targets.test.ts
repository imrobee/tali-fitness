import { describe, expect, it } from "vitest";
import { validateProfile } from "./targets";

const valid = { nickname: "Rob", calorieBudget: "1853", proteinGoal: "130" };

describe("validateProfile", () => {
  it("accepts targets inside the limits", () => {
    expect(validateProfile(valid)).toEqual({});
    expect(validateProfile({ ...valid, calorieBudget: "800", proteinGoal: "0" })).toEqual({});
  });

  it("accepts a nickname-only save that leaves targets empty", () => {
    expect(validateProfile({ nickname: "Rob", calorieBudget: "", proteinGoal: "" })).toEqual({});
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
