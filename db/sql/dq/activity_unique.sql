-- Strava ids that appear more than once in core.fact_activity. The UNIQUE constraint
-- should make this impossible; the check proves it stays that way. Fail on any.
SELECT
    count(*) AS observed_value,
    CASE WHEN count(*) = 0 THEN 'pass' ELSE 'fail' END AS status,
    'duplicate strava_ids: fail > 0' AS threshold
FROM (
    SELECT strava_id FROM core.fact_activity GROUP BY strava_id HAVING count(*) > 1
) AS duplicates;
