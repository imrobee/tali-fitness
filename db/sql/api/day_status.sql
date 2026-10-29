SELECT day, has_activity, calorie_status, recovery_logged, kind, lenient, state, counted, island_id
FROM mart.fn_day_status(:today);
