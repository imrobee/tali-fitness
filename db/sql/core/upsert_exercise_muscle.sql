-- One row of db/seeds/exercise_muscle_map.csv.
INSERT INTO core.exercise_muscle_map (exercise_name, muscle_group)
VALUES (:exercise_name, :muscle_group)
ON CONFLICT (exercise_name) DO UPDATE
SET muscle_group = EXCLUDED.muscle_group;
