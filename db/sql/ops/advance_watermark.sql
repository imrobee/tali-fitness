-- GREATEST: re-loading an older activity (inside the lookback window) never moves
-- the watermark backwards.
INSERT INTO ops.watermarks (source, value, updated_at)
VALUES (:source, :value, now())
ON CONFLICT (source) DO UPDATE
SET value      = GREATEST(ops.watermarks.value, EXCLUDED.value),
    updated_at = now();
