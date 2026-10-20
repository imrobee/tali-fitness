UPDATE ops.pipeline_runs
SET status        = 'failed',
    finished_at   = now(),
    error_message = :error_message
WHERE run_id = :run_id;
