// Response shapes from the API (ARCHITECTURE.md section 11; the server side is
// api/app/dashboard/models.py and api/app/me.py). Keep the two in step.

import type { CalorieStatus } from "../lib/ring";

/** Whether a day kept the streak (ARCHITECTURE.md 8.3). */
export type DayState = "counted" | "pending" | "at_risk" | "broken" | "future";

/** What kind of day it was: success, over budget, a rest day, or nothing logged. */
export type DayKind = "success" | "over" | "recovery" | "miss";

export type RecoveryState = "available" | "logged" | "blocked" | "counted" | "locked";

export interface StreakDay {
  date: string;
  weekday: string;
  state: DayState;
  kind: DayKind | null; // null for future days
  recovery_logged: boolean; // logged by hand: only then does today show the snowflake
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
  recovery: { state: RecoveryState };
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
  weight_goal_kg: number | null;
  weight_unit: "kg" | "lb";
  lenient_weekends: boolean;
  vacation: Period | null; // still running or still to come
  last_vacation: Period | null; // the latest one that has ended
  earliest_date: string;
}

export interface Period {
  from: string;
  to: string;
}

export interface MeUpdate {
  nickname?: string | null;
  targets?: Targets;
  weight_goal_kg?: number;
  weight_unit?: "kg" | "lb";
  lenient_weekends?: boolean;
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

// GET /calendar
export type CalendarView = "week" | "month";

export interface CalendarDay {
  date: string;
  in_period: boolean;
  future: boolean;
  activity_count: number;
  primary_activity_type: string | null;
  recovery: boolean;
}

export interface Calendar {
  view: CalendarView;
  today: string;
  period_start: string;
  period_end: string;
  previous: string | null;
  next: string | null;
  days: CalendarDay[];
}

// GET /trends/training and /trends/nutrition
export type Grain = "week" | "month";

export interface TrainingPeriod {
  start: string;
  end: string;
  current: boolean;
  sessions: number;
  active_s: number;
  run_m: number;
  volume_kg: number;
  prev_sessions: number | null;
  prev_active_s: number | null;
  active_change_pct: number | null;
}

export interface TrainingTrend {
  grain: Grain;
  periods: TrainingPeriod[];
}

export type PeriodStatus = "within" | "over" | "not_set" | "not_logged";

export interface NutritionPeriod {
  start: string;
  end: string;
  current: boolean;
  days_logged: number;
  avg_kcal: number | null;
  avg_protein_g: number | null;
  avg_budget: number | null;
  days_within: number;
  days_over: number;
  status: PeriodStatus;
  prev_avg_kcal: number | null;
}

export interface NutritionTrend {
  grain: Grain;
  rolling_7d: {
    end_date: string;
    kcal_avg: number | null;
    protein_avg_g: number | null;
    days_logged: number;
  };
  periods: NutritionPeriod[];
}

// GET /weight
export interface WeightDay {
  date: string;
  weight_kg: number | null;
  avg_7d_kg: number | null;
  change_7d_kg: number | null;
  goal_kg: number | null;
  status: "not_logged" | "not_set" | "at_or_below" | "above";
}

export interface Weight {
  from: string;
  to: string;
  latest_date: string | null;
  latest_kg: number | null;
  avg_7d_kg: number | null;
  change_7d_kg: number | null;
  goal_kg: number | null;
  to_goal_kg: number | null;
  days: WeightDay[];
}

// GET /records, /muscle-volume
export interface PersonalRecord {
  exercise: string;
  equipment: string | null;
  muscle_group: string | null; // null until the exercise is mapped to a muscle group
  e1rm_kg: number;
  weight_kg: number;
  reps: number;
  date: string;
  activity_id: number;
  prev_e1rm_kg: number | null;
  sessions: number;
  recent: boolean;
}

export interface MuscleWeek {
  muscle_group: string;
  sets: number;
  volume_kg: number;
  prev_sets: number;
  prev_volume_kg: number;
}

export interface MuscleVolume {
  week_start: string;
  week_end: string;
  groups: MuscleWeek[];
}

// POST/GET /sync/strava
export interface SyncStatus {
  requested_at: string | null;
  dag_run_id: string | null;
  state: "queued" | "running" | "success" | "failed" | null;
}
