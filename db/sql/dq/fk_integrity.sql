-- Fact rows pointing at a row that does not exist (orphans). Foreign keys should make
-- this impossible; the check proves it stays that way. Fail on any.
WITH orphans AS (
    SELECT count(*) AS n FROM core.fact_activity f
    WHERE NOT EXISTS (SELECT 1 FROM core.dim_date d WHERE d.date_key = f.date_key)
       OR NOT EXISTS (SELECT 1 FROM core.dim_activity_type t
                      WHERE t.activity_type_key = f.activity_type_key)
       OR NOT EXISTS (SELECT 1 FROM raw.strava_activities r WHERE r.strava_id = f.strava_id)
    UNION ALL
    SELECT count(*) FROM core.fact_set s
    WHERE NOT EXISTS (SELECT 1 FROM core.fact_activity a WHERE a.activity_key = s.activity_key)
       OR NOT EXISTS (SELECT 1 FROM core.dim_date d WHERE d.date_key = s.date_key)
       OR NOT EXISTS (SELECT 1 FROM core.dim_exercise e WHERE e.exercise_key = s.exercise_key)
    UNION ALL
    SELECT count(*) FROM core.fact_dietary_sample s
    WHERE NOT EXISTS (SELECT 1 FROM core.dim_date d WHERE d.date_key = s.date_key)
       OR NOT EXISTS (SELECT 1 FROM raw.health_batches b WHERE b.batch_id = s.batch_id)
)
SELECT
    sum(n) AS observed_value,
    CASE WHEN sum(n) = 0 THEN 'pass' ELSE 'fail' END AS status,
    'fact rows without their dimension or raw row: fail > 0' AS threshold
FROM orphans;
