-- A ready-made core row, so the demo needs no Airflow run.
INSERT INTO core.fact_activity (
    strava_id, date_key, activity_type_key, title, started_at, started_local, ended_at,
    tz, duration_s, source_fetched_at, parse_status
)
SELECT
    :id,
    :date_key,
    activity_type_key,
    :title,
    CAST(:started AS timestamptz),
    CAST(:local AS timestamp),
    CAST(:started AS timestamptz) + :seconds * interval '1 second',
    'Asia/Manila',
    :seconds,
    now(),
    'not_applicable'
FROM core.dim_activity_type
WHERE strava_sport_type = :sport
