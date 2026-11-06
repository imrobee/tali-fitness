-- The latest "Sync now" request for a source, for the cooldown and the page's status.
SELECT id, requested_at, airflow_run_id
FROM ops.sync_requests
WHERE source = :source
ORDER BY requested_at DESC
LIMIT 1;
