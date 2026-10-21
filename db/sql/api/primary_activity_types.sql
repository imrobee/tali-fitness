-- Per day, the type of the longest activity: it picks the streak circle's icon.
SELECT DISTINCT ON (d.date) d.date AS day, t.app_type
FROM core.fact_activity a
JOIN core.dim_date d USING (date_key)
JOIN core.dim_activity_type t USING (activity_type_key)
WHERE d.date BETWEEN :start AND :end
ORDER BY d.date, a.duration_s DESC, a.started_at;
