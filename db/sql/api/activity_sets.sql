-- The sets of one activity in workout order: each exercise entry, then its sets.
SELECT
    s.exercise_order,
    e.exercise_name,
    e.equipment,
    s.exercise_note,
    s.set_number,
    s.set_kind,
    s.weight_kg,
    s.orig_weight,
    s.orig_unit,
    s.reps,
    s.distance_m,
    s.duration_s
FROM core.fact_set s
JOIN core.dim_exercise e USING (exercise_key)
WHERE s.activity_key = :id
ORDER BY s.exercise_order, s.set_number;
