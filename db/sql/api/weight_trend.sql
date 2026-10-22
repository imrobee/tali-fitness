SELECT day, weight_kg, avg_7d_kg, change_7d_kg, goal_kg, status
FROM mart.fn_weight_trend(:start, :end);
