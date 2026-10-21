-- Information only: days in the last 14 (ending today in the profile's time zone) that
-- have a workout but no calories, so they could not count for the streak.
-- ops.dq_results allows only pass/warn/fail, so this always stores 'pass' with its count.
WITH today AS (
    SELECT CAST(CAST(:now AS timestamptz) AT TIME ZONE timezone AS date) AS day
    FROM app.profile
    WHERE id = 1
)
SELECT
    count(*) AS observed_value,
    'pass' AS status,
    'days with a workout but no calories, last 14 days: information only' AS threshold
FROM (
    SELECT DISTINCT d.date
    FROM core.fact_activity a
    JOIN core.dim_date d ON d.date_key = a.date_key
    CROSS JOIN today
    WHERE d.date BETWEEN today.day - 13 AND today.day
      AND NOT EXISTS (
          SELECT 1 FROM core.fact_dietary_sample s
          WHERE s.local_date = d.date AND s.sample_type = 'energy'
      )
) AS days;
