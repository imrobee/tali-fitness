UPDATE ops.quarantine
SET first_seen_at = CAST(:at AS timestamptz) + interval '20 seconds'
WHERE first_seen_at = now()
