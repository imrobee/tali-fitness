-- Hours since the Shortcut last reached the API successfully. Duplicate pushes count
-- (each writes a pipeline_runs row, DECISIONS D27): they prove the Shortcut is alive.
-- Warn after 48 h, fail after 96 h or if there has never been one.
WITH last_ok AS (
    SELECT max(finished_at) AS finished_at
    FROM ops.pipeline_runs
    WHERE source = 'health' AND status = 'success'
)
SELECT
    round(extract(epoch FROM CAST(:now AS timestamptz) - finished_at) / 3600, 2) AS observed_value,
    CASE
        WHEN finished_at IS NULL                                        THEN 'fail'
        WHEN CAST(:now AS timestamptz) - finished_at > interval '96 hours' THEN 'fail'
        WHEN CAST(:now AS timestamptz) - finished_at > interval '48 hours' THEN 'warn'
        ELSE 'pass'
    END AS status,
    'hours since last success: warn > 48, fail > 96' AS threshold
FROM last_ok;
