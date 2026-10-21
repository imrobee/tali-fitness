INSERT INTO core.fact_set (
    activity_key, date_key, exercise_key, exercise_order, set_number, set_kind,
    weight_kg, reps, distance_m, duration_s, orig_weight, orig_unit, exercise_note
)
VALUES (
    :activity_key, :date_key, :exercise_key, :exercise_order, :set_number, :set_kind,
    :weight_kg, :reps, :distance_m, :duration_s, :orig_weight, :orig_unit, :exercise_note
);
