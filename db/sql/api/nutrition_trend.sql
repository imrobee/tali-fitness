SELECT period_start, period_end, is_current, days_logged, avg_kcal, avg_protein_g, avg_budget,
       days_within, days_over, status, prev_avg_kcal
FROM mart.fn_nutrition_trend(:today, :grain, :periods);
