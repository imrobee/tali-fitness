-- Every activity in a date range, newest first, with the numbers the list summaries need.
-- Strength counts and volume come from the sets; other activities have none (0).
SELECT
    a.activity_key AS id,
    d.date AS day,
    t.app_type AS type,
    a.title,
    a.started_at,
    a.duration_s,
    a.moving_s,
    a.distance_m,
    a.parse_status,
    (SELECT count(DISTINCT s.exercise_order) FROM core.fact_set s
      WHERE s.activity_key = a.activity_key) AS exercise_count,
    (SELECT count(*) FROM core.fact_set s WHERE s.activity_key = a.activity_key) AS set_count,
    (SELECT coalesce(sum(s.volume_kg), 0) FROM core.fact_set s
      WHERE s.activity_key = a.activity_key) AS volume_kg
FROM core.fact_activity a
JOIN core.dim_date d USING (date_key)
JOIN core.dim_activity_type t USING (activity_type_key)
WHERE d.date BETWEEN :start AND :end
ORDER BY d.date DESC, a.started_at DESC;
