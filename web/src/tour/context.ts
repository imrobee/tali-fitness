// The tour's start button and the provider share this. Kept apart from TourProvider.tsx,
// which exports components only.

import { createContext, useContext } from "react";

export interface TourControls {
  start: () => void;
  running: boolean;
}

// Outside a TourProvider (most component tests), starting does nothing.
export const TourContext = createContext<TourControls>({ start: () => {}, running: false });

export function useTour(): TourControls {
  return useContext(TourContext);
}

// Shown once per browser on a first demo visit; the Tour button replays it any time.
const SEEN_KEY = "tali.tour-seen";

export function tourSeen(): boolean {
  try {
    return window.localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return true; // storage blocked: don't start on every page load
  }
}

export function markTourSeen(): void {
  try {
    window.localStorage.setItem(SEEN_KEY, "1");
  } catch {
    // Storage blocked: nothing to remember it in.
  }
}
