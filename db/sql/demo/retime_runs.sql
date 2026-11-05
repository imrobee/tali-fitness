-- The demo replays months of pipeline runs in seconds. The run bookkeeping uses the
-- database clock (now()), so after each replayed step, its rows are moved to the moment
-- the step stands for. Only rows written since the step began (:since) are touched.
UPDATE ops.pipeline_runs
SET started_at  = CAST(:at AS timestamptz),
    finished_at = CASE
        WHEN finished_at IS NULL THEN NULL
        ELSE CAST(:at AS timestamptz) + interval '25 seconds'
    END
WHERE started_at >= CAST(:since AS timestamptz)
   OR finished_at >= CAST(:since AS timestamptz)
