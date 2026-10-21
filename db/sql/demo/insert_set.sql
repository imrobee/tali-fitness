-- Only the columns a set kind uses are filled: the database's CHECK enforces the rest.
INSERT INTO core.fact_set (
    activity_key, date_key, exercise_key, exercise_order, set_number, set_kind,
    weight_kg, reps, distance_m, duration_s, orig_weight, orig_unit, exercise_note
)
SELECT
    activity_key, date_key, :exercise_key, :exercise_order, :set_number, :set_kind,
    CAST(:weight_kg AS numeric), :reps, CAST(:distance_m AS numeric), :duration_s,
    CAST(:orig_weight AS numeric), :orig_unit, :note
FROM core.fact_activity
WHERE strava_id = :strava_id
