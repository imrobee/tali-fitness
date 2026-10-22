// Data hooks (TanStack Query: caching, loading and error states, and a refetch whenever
// the app comes back into view, so the greeting and "today" stay correct; UI_SPEC.md 5.1).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type {
  ActivityDetail,
  ActivityList,
  Dashboard,
  Me,
  MeUpdate,
  PipelineHealth,
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

export function usePipelineHealth() {
  return useQuery({
    queryKey: ["pipeline-health"],
    queryFn: () => apiFetch<PipelineHealth>("/pipeline/health"),
  });
}

export function useSaveMe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: MeUpdate) =>
      apiFetch<Me>("/me", { method: "PUT", body: JSON.stringify(update) }),
    onSuccess: (me) => {
      queryClient.setQueryData(["me"], me);
      // Targets and the nickname change the dashboard too.
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
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
