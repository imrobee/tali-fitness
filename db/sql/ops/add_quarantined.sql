UPDATE ops.pipeline_runs
SET rows_quarantined = COALESCE(rows_quarantined, 0) + :count
WHERE run_id = :run_id;
