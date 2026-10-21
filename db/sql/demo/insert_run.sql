INSERT INTO ops.pipeline_runs (source, started_at, finished_at, status, error_message)
VALUES (:source, CAST(:at AS timestamptz), CAST(:at AS timestamptz), :status, :error)
RETURNING run_id
