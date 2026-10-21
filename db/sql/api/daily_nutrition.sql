SELECT day, kcal, protein_g, calorie_budget, protein_goal, calorie_status
FROM mart.fn_daily_nutrition(:start, :end);
