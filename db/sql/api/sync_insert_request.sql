INSERT INTO ops.sync_requests (source, requested_at, airflow_run_id)
VALUES (:source, :requested_at, :airflow_run_id)
RETURNING id;
