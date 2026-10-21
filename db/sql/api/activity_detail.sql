-- One activity, for the detail view. parse_status and the raw text tell the page whether
-- the sets below are the whole workout (UI_SPEC.md 6.1).
SELECT
    a.activity_key AS id,
    d.date AS day,
    t.app_type AS type,
    a.title,
    a.started_at,
    a.duration_s,
    a.distance_m,
    a.parse_status,
    CASE WHEN a.parse_status IS DISTINCT FROM 'ok' THEN a.description_raw END AS description_raw
FROM core.fact_activity a
JOIN core.dim_date d USING (date_key)
JOIN core.dim_activity_type t USING (activity_type_key)
WHERE a.activity_key = :id;
