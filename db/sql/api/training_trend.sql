SELECT period_start, period_end, is_current, sessions, active_s, run_m, volume_kg,
       prev_sessions, prev_active_s, active_change_pct
FROM mart.fn_training_trend(:today, :grain, :periods);
