-- Hours since the last successful Strava sync ('partial' counts: it made progress).
-- Warn after 6 h, fail after 24 h or if there has never been one.
WITH last_ok AS (
    SELECT max(finished_at) AS finished_at
    FROM ops.pipeline_runs
    WHERE source = 'strava' AND status IN ('success', 'partial')
)
SELECT
    round(extract(epoch FROM CAST(:now AS timestamptz) - finished_at) / 3600, 2) AS observed_value,
    CASE
        WHEN finished_at IS NULL                                        THEN 'fail'
        WHEN CAST(:now AS timestamptz) - finished_at > interval '24 hours' THEN 'fail'
        WHEN CAST(:now AS timestamptz) - finished_at > interval '6 hours'  THEN 'warn'
        ELSE 'pass'
    END AS status,
    'hours since last success: warn > 6, fail > 24' AS threshold
FROM last_ok;
