-- Demo reseed (app/demo/replay.py): empty every data table, so a reseed always starts
-- from the same blank warehouse. RESTART IDENTITY: run and batch ids come out the same
-- every time too. core.dim_date (the calendar) and app.profile (one row) are kept.
TRUNCATE
    raw.health_batches, raw.health_samples, raw.strava_activities,
    core.fact_activity, core.fact_set, core.fact_dietary_sample, core.fact_body_mass,
    core.dim_exercise, core.dim_activity_type, core.exercise_muscle_map,
    app.recovery_day, app.target_history, app.weight_goal_history,
    app.streak_settings_history, app.vacation, app.session,
    ops.quarantine, ops.pipeline_runs, ops.dq_results, ops.watermarks, ops.sync_requests,
    ops.oauth_tokens
RESTART IDENTITY CASCADE
