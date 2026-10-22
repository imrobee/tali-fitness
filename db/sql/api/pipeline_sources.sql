-- One row per pipeline source for the Me page's "Data and sync" panel (ARCHITECTURE.md 10).
-- Status uses the same thresholds as the freshness checks in db/sql/dq/: ok within warn,
-- delayed between warn and fail, failed beyond fail, never succeeded, or the last run failed.
-- Strava counts 'partial' runs as a success (it made progress); health counts 'success' only.
WITH sources(source, warn_hours, fail_hours) AS (
    VALUES ('strava', 6, 24), ('health', 48, 96)
),
last_success AS (
    SELECT r.source, max(r.finished_at) AS last_success_at
    FROM ops.pipeline_runs r
    WHERE r.status = 'success'
       OR (r.source = 'strava' AND r.status = 'partial')
    GROUP BY r.source
),
last_run AS (
    SELECT DISTINCT ON (source) source, status AS last_status
    FROM ops.pipeline_runs
    ORDER BY source, started_at DESC, run_id DESC
),
failures AS (
    SELECT source, count(*) AS failures_7d
    FROM ops.pipeline_runs
    WHERE status = 'failed' AND started_at >= CAST(:now AS timestamptz) - interval '7 days'
    GROUP BY source
)
SELECT
    s.source,
    ls.last_success_at,
    CASE
        WHEN lr.last_status = 'failed' OR ls.last_success_at IS NULL THEN 'failed'
        WHEN CAST(:now AS timestamptz) - ls.last_success_at > s.fail_hours * interval '1 hour'
            THEN 'failed'
        WHEN CAST(:now AS timestamptz) - ls.last_success_at > s.warn_hours * interval '1 hour'
            THEN 'delayed'
        ELSE 'ok'
    END AS status,
    coalesce(f.failures_7d, 0) AS failures_7d
FROM sources s
LEFT JOIN last_success ls ON ls.source = s.source
LEFT JOIN last_run lr ON lr.source = s.source
LEFT JOIN failures f ON f.source = s.source
ORDER BY s.source;
