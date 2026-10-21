-- Open quarantine rows, counted by reason (the Me page's "Quarantined records: N").
SELECT reason_code, count(*) AS open_count
FROM ops.quarantine
WHERE resolved_at IS NULL
GROUP BY reason_code
ORDER BY open_count DESC, reason_code;
