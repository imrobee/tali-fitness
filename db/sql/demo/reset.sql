-- Demo reseed (app/demo/replay.py): empty every data table, children before parents.
-- DELETE, not TRUNCATE: TRUNCATE locks a table against readers until the rebuild commits,
-- while DELETE lets visitors keep reading the old demo until the new one appears whole.
-- core.dim_date (the calendar) and app.profile (one row) are kept.
DO $$
BEGIN
    DELETE FROM core.fact_set;
    DELETE FROM core.fact_activity;
    DELETE FROM core.fact_dietary_sample;
    DELETE FROM core.fact_body_mass;
    DELETE FROM raw.health_samples;
    DELETE FROM raw.health_batches;
    DELETE FROM raw.strava_activities;
    DELETE FROM core.dim_exercise;
    DELETE FROM core.exercise_muscle_map;
    DELETE FROM core.dim_activity_type;
    DELETE FROM app.recovery_day;
    DELETE FROM app.target_history;
    DELETE FROM app.weight_goal_history;
    DELETE FROM app.streak_settings_history;
    DELETE FROM app.vacation;
    DELETE FROM app.session;
    DELETE FROM ops.dq_results;
    DELETE FROM ops.quarantine;
    DELETE FROM ops.pipeline_runs;
    DELETE FROM ops.watermarks;
    DELETE FROM ops.sync_requests;
    DELETE FROM ops.oauth_tokens;
    UPDATE app.profile SET nickname = NULL, weight_unit = 'kg';
END
$$
