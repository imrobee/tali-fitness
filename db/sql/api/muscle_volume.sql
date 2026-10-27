SELECT week_start, week_end, muscle_group, sets, volume_kg, prev_sets, prev_volume_kg
FROM mart.fn_muscle_volume(:today, 1);
