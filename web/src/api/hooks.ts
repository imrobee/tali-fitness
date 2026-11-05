// Data hooks (TanStack Query: caching, loading and error states, and a refetch whenever
// the app comes back into view, so the greeting and "today" stay correct; UI_SPEC.md 5.1).

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clearDemoSettings, loadDemoSettings, saveDemoSettings, withUpdate } from "../demo/settings";
import type { WeightUnit } from "../lib/units";
import { AUTH_QUERY } from "./auth";
import { apiFetch } from "./client";
import { useIsDemo } from "./visit";
import type {
  ActivityDetail,
  ActivityList,
  Calendar,
  CalendarView,
  Dashboard,
  Grain,
  Me,
  MeUpdate,
  MuscleVolume,
  PersonalRecord,
  NutritionTrend,
  Period,
  PipelineHealth,
  SyncStatus,
  TrainingTrend,
  Weight,
} from "./types";

/** `date` null means "today, as the server sees it". */
export function useDashboard(date: string | null) {
  return useQuery({
    queryKey: ["dashboard", date ?? "today"],
    queryFn: () => apiFetch<Dashboard>(date ? `/dashboard?date=${date}` : "/dashboard"),
  });
}

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => apiFetch<Me>("/me") });
}

/** The person's weight unit from the Me page; kg until /me has answered. */
export function useWeightUnit(): WeightUnit {
  return useMe().data?.weight_unit ?? "kg";
}

/** Activities from `from` to `to` (inclusive), grouped by day by the server. Waits for both. */
export function useActivities(from: string | null, to: string | null) {
  return useQuery({
    queryKey: ["activities", from, to],
    queryFn: () => apiFetch<ActivityList>(`/activities?from=${from}&to=${to}`),
    enabled: from !== null && to !== null,
  });
}

/** One activity's sets. Fetched only when its row is opened (`id` null = not yet). */
export function useActivity(id: number | null) {
  return useQuery({
    queryKey: ["activity", id],
    queryFn: () => apiFetch<ActivityDetail>(`/activities/${id}`),
    enabled: id !== null,
  });
}

/** The week or month that contains `date` (null = the one containing today). */
export function useCalendar(view: CalendarView, date: string | null) {
  return useQuery({
    queryKey: ["calendar", view, date ?? "today"],
    queryFn: () => apiFetch<Calendar>(`/calendar?view=${view}${date ? `&date=${date}` : ""}`),
    // Keep the old grid on screen while the next month loads, so the card does not jump.
    placeholderData: keepPreviousData,
  });
}

export function useTrainingTrend(grain: Grain) {
  return useQuery({
    queryKey: ["trends", "training", grain],
    queryFn: () => apiFetch<TrainingTrend>(`/trends/training?grain=${grain}`),
    placeholderData: keepPreviousData,
  });
}

export function useNutritionTrend(grain: Grain) {
  return useQuery({
    queryKey: ["trends", "nutrition", grain],
    queryFn: () => apiFetch<NutritionTrend>(`/trends/nutrition?grain=${grain}`),
    placeholderData: keepPreviousData,
  });
}

/** The server's default range (the last 90 days). */
export function useWeight() {
  return useQuery({
    queryKey: ["weight"],
    queryFn: () => apiFetch<Weight>("/weight"),
    placeholderData: keepPreviousData,
  });
}

export function useRecords() {
  return useQuery({
    queryKey: ["records"],
    queryFn: () => apiFetch<{ records: PersonalRecord[] }>("/records"),
  });
}

export function useMuscleVolume() {
  return useQuery({ queryKey: ["muscle-volume"], queryFn: () => apiFetch<MuscleVolume>("/muscle-volume") });
}

/** The last "Sync now" run. Polled every 3 s while Airflow is still working on it. */
export function useSyncStatus() {
  return useQuery({
    queryKey: ["sync-strava"],
    queryFn: () => apiFetch<SyncStatus>("/sync/strava"),
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state === "queued" || state === "running" ? 3000 : false;
    },
  });
}

export function useSyncNow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<SyncStatus>("/sync/strava", { method: "POST" }),
    // Follow the new run straight away, then ask Airflow for its state without waiting
    // for the first 3-second poll.
    onSuccess: (status) => {
      queryClient.setQueryData(["sync-strava"], status);
      queryClient.invalidateQueries({ queryKey: ["sync-strava"] });
    },
  });
}

export function usePipelineHealth() {
  return useQuery({
    queryKey: ["pipeline-health"],
    queryFn: () => apiFetch<PipelineHealth>("/pipeline/health"),
  });
}

export function useSaveMe() {
  const queryClient = useQueryClient();
  const demo = useIsDemo();
  return useMutation({
    mutationFn: (update: MeUpdate) => {
      if (demo) {
        // The demo keeps it in this tab and sends it with every request; nothing is saved.
        saveDemoSettings(withUpdate(loadDemoSettings(), update));
        return apiFetch<Me>("/me");
      }
      return apiFetch<Me>("/me", { method: "PUT", body: JSON.stringify(update) });
    },
    onSuccess: (me) => {
      queryClient.setQueryData(["me"], me);
      if (demo) {
        // A demo budget applies to every past day too: every page reads again.
        queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== AUTH_QUERY[0] });
      } else {
        // Targets and the nickname change the dashboard too.
        queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      }
    },
  });
}

/** The demo's Reset button: back to the demo's own settings on every page. */
export function useResetDemo(): () => void {
  const queryClient = useQueryClient();
  return () => {
    clearDemoSettings();
    queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== AUTH_QUERY[0] });
  };
}

/** Set or end the vacation or injury break; the streak and the Me page both change. */
export function useVacation() {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  const save = useMutation({
    mutationFn: (period: Period) =>
      apiFetch<Me>("/vacation", { method: "PUT", body: JSON.stringify(period) }),
    onSuccess: (me) => {
      queryClient.setQueryData(["me"], me);
      refresh();
    },
  });
  const end = useMutation({
    mutationFn: () => apiFetch("/vacation", { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      refresh();
    },
  });
  return { save, end };
}

export function useRecovery() {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  const log = useMutation({
    mutationFn: (date: string) =>
      apiFetch("/recovery", { method: "POST", body: JSON.stringify({ date }) }),
    onSuccess: refresh,
  });
  const undo = useMutation({
    mutationFn: (date: string) => apiFetch(`/recovery/${date}`, { method: "DELETE" }),
    onSuccess: refresh,
  });
  return { log, undo };
}
