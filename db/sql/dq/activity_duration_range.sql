-- Activities whose duration is zero or longer than a day: likely a watch left running
-- or a broken record. Worth a look, not a broken pipeline: warn on any.
SELECT
    count(*) AS observed_value,
    CASE WHEN count(*) = 0 THEN 'pass' ELSE 'warn' END AS status,
    'activities outside 0 < duration_s <= 86400: warn > 0' AS threshold
FROM core.fact_activity
WHERE NOT (duration_s > 0 AND duration_s <= 86400);
