-- Activities missing a field every page relies on. NOT NULL constraints should make
-- this impossible; the check proves it stays that way. Fail on any.
SELECT
    count(*) AS observed_value,
    CASE WHEN count(*) = 0 THEN 'pass' ELSE 'fail' END AS status,
    'activities missing started_at, date_key or duration_s: fail > 0' AS threshold
FROM core.fact_activity
WHERE started_at IS NULL OR date_key IS NULL OR duration_s IS NULL;
