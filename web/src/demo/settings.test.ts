// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import {
  clearDemoSettings,
  demoSettingsHeader,
  HEADER,
  loadDemoSettings,
  saveDemoSettings,
  withUpdate,
} from "./settings";

afterEach(() => sessionStorage.clear());

describe("a demo visitor's settings", () => {
  it("send nothing until something is changed", () => {
    expect(demoSettingsHeader()).toEqual({});
  });

  it("add each Me page save on top of the last", () => {
    let settings = withUpdate({}, { targets: { calorie_budget: 1700, protein_goal: 120 } });
    settings = withUpdate(settings, { lenient_weekends: true });

    expect(settings).toEqual({ calorie_budget: 1700, protein_goal: 120, lenient_weekends: true });
  });

  it("live in this tab, ride along as a header, and clear with Reset", () => {
    saveDemoSettings({ calorie_budget: 1700 });

    expect(loadDemoSettings()).toEqual({ calorie_budget: 1700 });
    expect(demoSettingsHeader()).toEqual({ [HEADER]: '{"calorie_budget":1700}' });
    clearDemoSettings();
    expect(demoSettingsHeader()).toEqual({});
  });

  it("are empty when the stored value is unreadable", () => {
    sessionStorage.setItem("tali.demo-settings", "{not json");

    expect(loadDemoSettings()).toEqual({});
  });
});
