// Data hooks (TanStack Query: caching, loading and error states, and a refetch whenever
// the app comes back into view, so the greeting and "today" stay correct; UI_SPEC.md 5.1).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Dashboard, Me, MeUpdate } from "./types";

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
