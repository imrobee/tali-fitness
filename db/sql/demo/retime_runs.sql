-- The demo replays months of pipeline runs in seconds, in one transaction. Bookkeeping
-- stamped with now() is moved to the moment the replayed step stands for. now() is fixed
-- for the whole transaction, so "= now()" picks out exactly this step's new rows.
UPDATE ops.pipeline_runs
SET started_at  = CAST(:at AS timestamptz),
    finished_at = CASE
        WHEN finished_at IS NULL THEN NULL
        ELSE CAST(:at AS timestamptz) + interval '25 seconds'
    END
WHERE started_at = now() OR finished_at = now()
