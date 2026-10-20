-- Land one Strava activity. Re-fetching the same activity replaces the stored copy,
-- so running the sync twice never creates duplicates.
INSERT INTO raw.strava_activities (strava_id, payload, fetched_at)
VALUES (:strava_id, CAST(:payload AS jsonb), :fetched_at)
ON CONFLICT (strava_id) DO UPDATE
SET payload    = EXCLUDED.payload,
    fetched_at = EXCLUDED.fetched_at;
