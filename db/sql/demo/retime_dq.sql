UPDATE ops.dq_results
SET checked_at = CAST(:at AS timestamptz) + interval '20 seconds'
WHERE checked_at = now()
