-- Last task of every run (trigger rule ALL_DONE). A run still 'running' here never
-- reached its end: a task was skipped, killed, or timed out.
UPDATE ops.pipeline_runs
SET status        = 'failed',
    finished_at   = now(),
    error_message = COALESCE(error_message, 'run ended before the sync finished')
WHERE run_id = :run_id
  AND status = 'running';
