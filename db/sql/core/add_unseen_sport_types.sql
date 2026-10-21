-- Sport types Strava sent that the seed CSV does not list: add them as 'other' so every
-- activity has a type. Adding one to the CSV later updates it (upsert_activity_type.sql).
INSERT INTO core.dim_activity_type (strava_sport_type, app_type, label)
SELECT DISTINCT payload->>'sport_type', 'other', payload->>'sport_type'
FROM raw.strava_activities
ON CONFLICT (strava_sport_type) DO NOTHING;
