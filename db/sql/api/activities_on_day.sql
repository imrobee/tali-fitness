-- The selected day's activities, most recent first (UI_SPEC.md 5.5).
SELECT a.activity_key AS id, t.app_type AS type, a.title, a.started_at, a.tz, a.duration_s
FROM core.fact_activity a
JOIN core.dim_activity_type t USING (activity_type_key)
WHERE a.date_key = :date_key
ORDER BY a.started_at DESC;
