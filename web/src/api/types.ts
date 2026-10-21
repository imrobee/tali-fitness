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
    bars: WeekBar[];
  };
}

/** One day of the weekly calorie card (UI_SPEC.md 5.8). */
export interface WeekBar {
  date: string;
  kcal: number | null;
  budget: number | null;
  status: BarStatus;
}

export type BarStatus = "within" | "over" | "not_set" | "not_logged" | "future";

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

// GET /api/v1/pipeline/health (api/app/pipeline.py).
export interface SourceHealth {
  source: string;
  last_success_at: string | null;
  status: "ok" | "delayed" | "failed";
  failures_7d: number;
}

export interface QuarantineItem {
  source: string;
  entity_id: string;
  line_no: number | null;
  reason_code: string;
  raw_snippet: string;
  first_seen_at: string;
}

export interface DqCheck {
  check_name: string;
  status: "pass" | "warn" | "fail";
  observed_value: number | null;
  threshold: string;
  checked_at: string;
}

export interface PipelineHealth {
  /** The server's clock; "ago" times are measured from it, not the phone's clock. */
  now: string;
  sources: SourceHealth[];
  quarantine: { open: number; by_reason: Record<string, number>; recent: QuarantineItem[] };
  dq: {
    passed: number;
    warnings: number;
    failed: number;
    checked_at: string | null;
    checks: DqCheck[];
  };
}

// GET /api/v1/activities and /activities/{id} (api/app/activities.py).
export interface ActivitySummary {
  id: number;
  type: string;
  title: string | null;
  started_at: string;
  duration_s: number;
  moving_s: number | null;
  distance_m: number | null;
  parse_status: string | null;
  exercise_count: number;
  set_count: number;
  volume_kg: number;
}

export interface ActivityDay {
  date: string;
  activities: ActivitySummary[];
}

export interface ActivityList {
  from: string;
  to: string;
  days: ActivityDay[];
}

export interface ActivitySet {
  number: number;
  kind: string;
  weight_kg: number | null;
  orig_weight: number | null;
  orig_unit: string | null;
  reps: number | null;
  distance_m: number | null;
  duration_s: number | null;
}

export interface ActivityExercise {
  order: number;
  name: string;
  equipment: string | null;
  note: string | null;
  sets: ActivitySet[];
}

export interface ActivityDetail {
  id: number;
  date: string;
  type: string;
  title: string | null;
  started_at: string;
  duration_s: number;
  distance_m: number | null;
  parse_status: string | null;
  description_raw: string | null;
  exercises: ActivityExercise[];
}
