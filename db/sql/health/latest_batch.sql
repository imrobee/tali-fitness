-- The most recent batch for the same window, used to spot an identical re-send.
SELECT batch_id, payload_sha256
FROM raw.health_batches
WHERE window_start = :window_start
  AND window_end = :window_end
ORDER BY received_at DESC
LIMIT 1;
