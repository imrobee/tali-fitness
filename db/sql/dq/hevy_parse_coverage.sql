-- Percent of Hevy activities in the last 30 days that parsed fully ('ok' vs 'partial').
-- No Hevy activities in the window means nothing to check: pass with no value.
-- Warn below 95%, fail below 80%.
WITH hevy AS (
    SELECT parse_status
    FROM core.fact_activity
    WHERE parse_status IN ('ok', 'partial')
      AND started_at >= CAST(:now AS timestamptz) - interval '30 days'
),
coverage AS (
    SELECT round(100.0 * count(*) FILTER (WHERE parse_status = 'ok') / NULLIF(count(*), 0), 1)
        AS percent_ok
    FROM hevy
)
SELECT
    percent_ok AS observed_value,
    CASE
        WHEN percent_ok IS NULL THEN 'pass'
        WHEN percent_ok < 80    THEN 'fail'
        WHEN percent_ok < 95    THEN 'warn'
        ELSE 'pass'
    END AS status,
    'percent of Hevy activities parsed ok, last 30 days: warn < 95, fail < 80' AS threshold
FROM coverage;
