INSERT INTO raw.strava_activities (strava_id, payload, fetched_at)
VALUES (:id, CAST(:payload AS jsonb), now())
