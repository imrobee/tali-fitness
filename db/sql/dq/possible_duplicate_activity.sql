-- Pairs of activities on the same day whose time ranges overlap: maybe one session
-- recorded twice (for example the Apple Watch and Hevy). A cheap guard, never merged
-- automatically (ARCHITECTURE.md 14 #4). Warn on any.
SELECT
    count(*) AS observed_value,
    CASE WHEN count(*) = 0 THEN 'pass' ELSE 'warn' END AS status,
    'overlapping activity pairs on one day: warn > 0' AS threshold
FROM core.fact_activity a
JOIN core.fact_activity b
    ON  a.date_key = b.date_key
    AND a.activity_key < b.activity_key   -- each pair once
    AND a.started_at < b.ended_at
    AND b.started_at < a.ended_at;
