-- status is 'success', or 'partial' when the run stopped at its fetch cap
-- and the next run will continue.
UPDATE ops.pipeline_runs
SET status        = :status,
    finished_at   = now(),
    rows_read     = :rows_read,
    rows_written  = :rows_written,
    error_message = NULL
WHERE run_id = :run_id;
