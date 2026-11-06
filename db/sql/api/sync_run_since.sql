-- The newest Strava run that started at or after a Sync now request: its progress when
-- GitHub Actions ran it (D133). Both schedulers write these rows (include/runs.py).
SELECT status
FROM ops.pipeline_runs
WHERE source = 'strava'
  AND started_at >= CAST(:since AS timestamptz)
ORDER BY started_at DESC
LIMIT 1;
