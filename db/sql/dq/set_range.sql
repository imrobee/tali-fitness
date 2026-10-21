-- Sets with an implausible value in a column that is present (NULL means the set kind
-- does not use it). Likely a typo in Hevy or a parser misread: warn on any.
SELECT
    count(*) AS observed_value,
    CASE WHEN count(*) = 0 THEN 'pass' ELSE 'warn' END AS status,
    'sets outside 0 < kg <= 500, 1 <= reps <= 200, 0 < m <= 300000, 0 < s <= 21600: warn > 0'
        AS threshold
FROM core.fact_set
WHERE NOT (weight_kg > 0 AND weight_kg <= 500)
   OR NOT (reps BETWEEN 1 AND 200)
   OR NOT (distance_m > 0 AND distance_m <= 300000)
   OR NOT (duration_s > 0 AND duration_s <= 21600);
-- NOT (NULL comparison) is NULL, so a NULL column never counts as an outlier.
