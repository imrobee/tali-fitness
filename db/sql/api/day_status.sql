SELECT day, has_activity, calorie_status, kind, lenient, state, counted, island_id
FROM mart.fn_day_status(:today);
