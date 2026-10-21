-- Days whose eaten calories add up to more than 10,000 kcal: likely a food logged with
-- the wrong serving size. Each sample is capped by a CHECK, but a day's total is not.
-- Warn on any.
WITH daily AS (
    SELECT local_date, sum(value) AS kcal
    FROM core.fact_dietary_sample
    WHERE sample_type = 'energy'
    GROUP BY local_date
)
SELECT
    count(*) AS observed_value,
    CASE WHEN count(*) = 0 THEN 'pass' ELSE 'warn' END AS status,
    'days with more than 10000 kcal: warn > 0' AS threshold
FROM daily
WHERE kcal > 10000;
