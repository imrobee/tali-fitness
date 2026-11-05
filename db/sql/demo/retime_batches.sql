UPDATE raw.health_batches
SET received_at = CAST(:at AS timestamptz),
    applied_at  = CASE
        WHEN applied_at IS NULL THEN NULL
        ELSE CAST(:at AS timestamptz) + interval '1 second'
    END
WHERE received_at = now()
