-- Without a calorie budget every day is 'not_set' (no ring, no over/within).
-- Warn when no target has ever been saved.
SELECT
    count(*) AS observed_value,
    CASE WHEN count(*) = 0 THEN 'warn' ELSE 'pass' END AS status,
    'saved targets: warn if 0' AS threshold
FROM app.target_history;
