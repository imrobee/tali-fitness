UPDATE ops.watermarks
SET updated_at = CAST(:at AS timestamptz)
WHERE updated_at = now()
