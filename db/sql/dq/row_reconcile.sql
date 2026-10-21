-- Every landed Strava activity should reach core: raw count minus core count.
-- The transform runs right after the sync, so any difference means a broken load.
SELECT
    (SELECT count(*) FROM raw.strava_activities) - (SELECT count(*) FROM core.fact_activity)
        AS observed_value,
    CASE
        WHEN (SELECT count(*) FROM raw.strava_activities) = (SELECT count(*) FROM core.fact_activity)
        THEN 'pass' ELSE 'fail'
    END AS status,
    'raw minus core activities: fail if not 0' AS threshold;
