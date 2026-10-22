-- Quarantined records nobody has looked at yet. A few are normal (a new Hevy format);
-- many mean something changed upstream. Warn above 0, fail above 25.
SELECT
    count(*) AS observed_value,
    CASE
        WHEN count(*) > 25 THEN 'fail'
        WHEN count(*) > 0  THEN 'warn'
        ELSE 'pass'
    END AS status,
    'open quarantine rows: warn > 0, fail > 25' AS threshold
FROM ops.quarantine
WHERE resolved_at IS NULL;
