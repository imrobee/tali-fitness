-- Copy every raw Strava activity into core.fact_activity, one row per strava_id.
-- start_date_local is wall-clock time despite its trailing "Z" (DECISIONS D3): the Z is
-- stripped and the value is never treated as UTC.
-- parse_status is not decided here: the Hevy parser sets it. A re-fetched activity keeps
-- its status until the parser runs again (source_fetched_at <> parsed_fetched_at).
INSERT INTO core.fact_activity (
    strava_id, date_key, activity_type_key, title, started_at, started_local, ended_at, tz,
    duration_s, moving_s, distance_m, avg_hr, calories_burned, description_raw,
    source_fetched_at
)
SELECT
    r.strava_id,
    to_char(local.started_local, 'YYYYMMDD')::int,
    t.activity_type_key,
    r.payload->>'name',
    (r.payload->>'start_date')::timestamptz,
    local.started_local,
    (r.payload->>'start_date')::timestamptz
        + (r.payload->>'elapsed_time')::int * interval '1 second',
    split_part(r.payload->>'timezone', ') ', 2),       -- "(GMT+08:00) Asia/Manila"
    (r.payload->>'elapsed_time')::int,
    (r.payload->>'moving_time')::int,
    (r.payload->>'distance')::numeric,
    (r.payload->>'average_heartrate')::numeric,
    (r.payload->>'calories')::numeric,
    r.payload->>'description',
    r.fetched_at
FROM raw.strava_activities r
CROSS JOIN LATERAL (
    SELECT rtrim(r.payload->>'start_date_local', 'Z')::timestamp AS started_local
) AS local
JOIN core.dim_activity_type t ON t.strava_sport_type = r.payload->>'sport_type'
ON CONFLICT (strava_id) DO UPDATE
SET date_key          = EXCLUDED.date_key,
    activity_type_key = EXCLUDED.activity_type_key,
    title             = EXCLUDED.title,
    started_at        = EXCLUDED.started_at,
    started_local     = EXCLUDED.started_local,
    ended_at          = EXCLUDED.ended_at,
    tz                = EXCLUDED.tz,
    duration_s        = EXCLUDED.duration_s,
    moving_s          = EXCLUDED.moving_s,
    distance_m        = EXCLUDED.distance_m,
    avg_hr            = EXCLUDED.avg_hr,
    calories_burned   = EXCLUDED.calories_burned,
    description_raw   = EXCLUDED.description_raw,
    source_fetched_at = EXCLUDED.source_fetched_at;
