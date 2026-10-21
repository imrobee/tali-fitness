-- Works for exercises with no equipment too: the constraint is NULLS NOT DISTINCT.
INSERT INTO core.dim_exercise (exercise_name, equipment)
VALUES (:exercise_name, :equipment)
ON CONFLICT ON CONSTRAINT dim_exercise_name_equipment_key DO NOTHING;
