import { describe, expect, it } from "vitest";
import { bodyWeight, fromKg, toKg, volume, weightNumber } from "./units";

describe("weight units", () => {
  it("converts with the exact pound", () => {
    expect(toKg(165, "lb")).toBeCloseTo(74.84274105, 8);
    expect(fromKg(74.84274105, "lb")).toBeCloseTo(165, 8);
    expect(fromKg(74.8, "kg")).toBe(74.8);
  });

  it("reads a goal typed in pounds back as the same number", () => {
    const stored = Math.round(toKg(160, "lb") * 1000) / 1000; // the database keeps 3 decimals
    expect(weightNumber(stored, "lb")).toBe("160");
  });

  it("shows body weight with one decimal and volume in whole units", () => {
    expect(bodyWeight(74.84274105, "kg")).toBe("74.8 kg");
    expect(bodyWeight(74.84274105, "lb")).toBe("165.0 lb");
    expect(volume(3490.9, "kg")).toBe("3,491 kg");
    expect(volume(3490.9, "lb")).toBe("7,696 lb");
  });
});
