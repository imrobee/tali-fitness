INSERT INTO core.dim_exercise (exercise_name, equipment, muscle_group)
VALUES (:name, :equipment, :muscle_group)
ON CONFLICT (exercise_name, equipment) DO UPDATE SET muscle_group = EXCLUDED.muscle_group
RETURNING exercise_key
