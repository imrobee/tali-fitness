-- Which of the listed activities are already in raw? Those are refreshed only after
-- new activities have been fetched, so the per-run cap always makes progress.
SELECT strava_id
FROM raw.strava_activities
WHERE strava_id = ANY(CAST(:ids AS bigint[]));
