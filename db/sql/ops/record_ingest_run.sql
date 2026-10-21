-- One finished run per ingest request (pushed data has no Airflow run to track).
INSERT INTO ops.pipeline_runs
    (source, started_at, finished_at, status, rows_read, rows_written, rows_quarantined)
VALUES
    (:source, :started_at, now(), 'success', :rows_read, :rows_written, :rows_quarantined);
