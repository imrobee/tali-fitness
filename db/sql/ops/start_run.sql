INSERT INTO ops.pipeline_runs (source, started_at, status, airflow_run_id)
VALUES (:source, now(), 'running', :airflow_run_id)
RETURNING run_id;
