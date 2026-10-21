// Response shapes from the API (ARCHITECTURE.md section 11; the server side is
// api/app/dashboard/models.py and api/app/me.py). Keep the two in step.

import type { CalorieStatus } from "../lib/ring";

export type DayState =
  | "qualifying"
  | "recovery"
  | "today_pending"
  | "at_risk"
  | "missed"
  | "future";

export type RecoveryState = "available" | "logged" | "no_freeze" | "blocked" | "counted" | "locked";

export interface StreakDay {
  date: string;
  weekday: string;
  state: DayState;
  primary_activity_type: string | null;
  calorie_status: CalorieStatus;
}

export interface Exercise {
  id: number;
  type: string;
  title: string | null;
  started_at: string;
  duration_s: number;
}

export interface Dashboard {
  today: string;
  selected_date: string;
  earliest_date: string;
  greeting: string;
  nickname: string | null;
  streak: { count: number; at_risk: boolean; message: string | null; week: StreakDay[] };
  recovery: { state: RecoveryState; freezes_left: number; freezes_max: number };
  exercises: Exercise[];
  calories: {
    eaten: number;
    budget: number | null;
    remaining: number | null;
    over: number | null;
    status: CalorieStatus;
  };
  protein: { grams: number; goal: number | null; percent: number | null };
  week_chart: {
    week_start: string;
    bars: { date: string; kcal: number | null; budget: number | null; status: string }[];
  };
}

export interface Targets {
  calorie_budget: number;
  protein_goal: number;
}

export interface Me {
  nickname: string | null;
  timezone: string;
  targets: (Targets & { effective_from: string }) | null;
  earliest_date: string;
}

export interface MeUpdate {
  nickname?: string | null;
  targets?: Targets;
}
