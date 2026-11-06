// A demo visitor's own Me settings (DECISIONS D122): kept in this browser tab only
// (sessionStorage: gone when the tab closes), sent with every API request, and applied by
// the demo server at read time. Never saved anywhere. Rob's own app never stores any, so
// it never sends the header.

import type { MeUpdate } from "../api/types";

export interface DemoSettings {
  calorie_budget?: number;
  protein_goal?: number;
  weight_goal_kg?: number;
  weight_unit?: "kg" | "lb";
  lenient_weekends?: boolean;
  nickname?: string;
}

const KEY = "tali.demo-settings";
export const HEADER = "X-Demo-Settings";

export function loadDemoSettings(): DemoSettings {
  try {
    return JSON.parse(window.sessionStorage.getItem(KEY) ?? "{}") as DemoSettings;
  } catch {
    return {}; // storage blocked or unreadable: no settings of your own
  }
}

export function saveDemoSettings(settings: DemoSettings): void {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(settings));
  } catch {
    // Storage blocked: the change can't be kept, and the pages keep the demo's values.
  }
}

export function clearDemoSettings(): void {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    // Storage blocked: there was nothing kept.
  }
}

/** The settings after a Me page save, on top of the ones already chosen. */
export function withUpdate(settings: DemoSettings, update: MeUpdate): DemoSettings {
  const next: DemoSettings = { ...settings };
  if (update.nickname !== undefined && update.nickname !== null) next.nickname = update.nickname;
  if (update.targets) {
    next.calorie_budget = update.targets.calorie_budget;
    next.protein_goal = update.targets.protein_goal;
  }
  if (update.weight_goal_kg !== undefined) next.weight_goal_kg = update.weight_goal_kg;
  if (update.weight_unit) next.weight_unit = update.weight_unit;
  if (update.lenient_weekends !== undefined) next.lenient_weekends = update.lenient_weekends;
  return next;
}

/** The header for apiFetch: nothing when no setting was changed. */
export function demoSettingsHeader(settings: DemoSettings = loadDemoSettings()): Record<string, string> {
  return Object.keys(settings).length > 0 ? { [HEADER]: JSON.stringify(settings) } : {};
}
