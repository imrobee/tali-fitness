-- Primary muscle group per exercise; exercises missing from the map stay 'Unmapped'
-- (the unmapped_exercises DQ check reports them).
UPDATE core.dim_exercise e
SET muscle_group = COALESCE(
    (SELECT m.muscle_group FROM core.exercise_muscle_map m WHERE m.exercise_name = e.exercise_name),
    'Unmapped'
);
