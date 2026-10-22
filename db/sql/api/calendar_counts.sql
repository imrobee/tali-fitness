-- How many activities each day in a date range has (days without any are left out).
SELECT d.date AS day, count(*)::integer AS activity_count
FROM core.fact_activity a
JOIN core.dim_date d USING (date_key)
WHERE d.date BETWEEN :start AND :end
GROUP BY d.date;
