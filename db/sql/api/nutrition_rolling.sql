SELECT day, kcal_avg_7d, protein_avg_7d, days_logged_7d
FROM mart.fn_nutrition_rolling(:day, :day);
