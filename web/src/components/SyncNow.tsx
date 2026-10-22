import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useSyncNow, useSyncStatus } from "../api/hooks";
import styles from "./DataSyncCard.module.css";

/**
 * "Sync now" for Strava (PROJECT_PLAN 7c): asks the API to start the strava_sync DAG, shows
 * "Syncing..." while Airflow works, then reloads every page's data once the run ends.
 */
export function SyncNowButton() {
  const queryClient = useQueryClient();
  const status = useSyncStatus();
  const sync = useSyncNow();
  // Only the run started from this screen is followed: the one this button's request made.
  const followed = sync.data?.dag_run_id ?? null;
  const state = status.data?.dag_run_id === followed ? (status.data?.state ?? null) : null;
  const busy = sync.isPending || state === "queued" || state === "running";
  const reloadedFor = useRef<string | null>(null);

  useEffect(() => {
    if (followed && (state === "success" || state === "failed") && reloadedFor.current !== followed) {
      reloadedFor.current = followed;
      queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== "sync-strava" });
    }
  }, [followed, state, queryClient]);

  let message = "";
  if (busy) message = "Syncing with Strava...";
  else if (sync.isError) message = sync.error.message;
  else if (state === "success") message = "Synced. New activities are in.";
  else if (state === "failed") message = "The sync failed. Airflow has the details.";

  return (
    <div className={styles.action}>
      <button
        type="button"
        className={styles.actionButton}
        disabled={busy}
        onClick={() => sync.mutate()}
      >
        {busy ? "Syncing..." : "Sync now"}
      </button>
      <span className={styles.meta} role="status">
        {message}
      </span>
    </div>
  );
}

/**
 * The server cannot reach the phone, so Apple Health is synced by running the Shortcut;
 * this opens it from Safari (UI_SPEC.md 6.3).
 */
export function RunHealthShortcut() {
  return (
    <div className={styles.action}>
      <a className={styles.actionButton} href="shortcuts://run-shortcut?name=Health%20Push">
        Run Health Push
      </a>
    </div>
  );
}
