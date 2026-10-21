INSERT INTO raw.health_batches (window_start, window_end, device_tz, payload_sha256, payload)
VALUES (:day, :day, 'Asia/Manila', 'demo', '{}')
RETURNING batch_id
