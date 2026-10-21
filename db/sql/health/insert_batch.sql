INSERT INTO raw.health_batches (window_start, window_end, device_tz, payload_sha256, payload)
VALUES (:window_start, :window_end, :device_tz, :payload_sha256, CAST(:payload AS jsonb))
RETURNING batch_id;
