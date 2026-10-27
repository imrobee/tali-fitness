-- A Strava run still marked running, started recently enough to be real: the DAG times
-- out after 20 minutes and close_run marks the rest failed, so an older "running" row is
-- a crash leftover and must not block the button forever.
SELECT EXISTS (
    SELECT 1 FROM ops.pipeline_runs
    WHERE source = 'strava'
      AND status = 'running'
      AND started_at > CAST(:now AS timestamptz) - interval '30 minutes'
) AS running;
