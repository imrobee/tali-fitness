-- Results of the most recent data-quality run that wrote any results.
SELECT check_name, status, observed_value, threshold, checked_at
FROM ops.dq_results
WHERE run_id = (
    SELECT run_id FROM ops.dq_results WHERE run_id IS NOT NULL ORDER BY id DESC LIMIT 1
)
ORDER BY id;
