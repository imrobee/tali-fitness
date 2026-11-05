-- The profile, with a demo visitor's own nickname and weight unit if they set them.
SELECT
    COALESCE(app.demo_setting('nickname'), nickname) AS nickname,
    timezone,
    COALESCE(app.demo_setting('weight_unit'), weight_unit) AS weight_unit
FROM app.profile
WHERE id = 1;
