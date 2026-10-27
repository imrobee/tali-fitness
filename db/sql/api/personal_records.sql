SELECT exercise_key, exercise_name, equipment, muscle_group, best_e1rm_kg, weight_kg, reps,
       day, activity_key, prev_e1rm_kg, sessions
FROM mart.fn_personal_records(:today);
