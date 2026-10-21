-- One row of db/seeds/dim_activity_type.csv. Editing the CSV takes effect next run.
INSERT INTO core.dim_activity_type (strava_sport_type, app_type, label)
VALUES (:strava_sport_type, :app_type, :label)
ON CONFLICT (strava_sport_type) DO UPDATE
SET app_type = EXCLUDED.app_type,
    label    = EXCLUDED.label;
