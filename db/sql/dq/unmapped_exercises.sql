-- Exercises with no muscle group yet: add them to db/seeds/exercise_muscle_map.csv.
-- Warn on any.
SELECT
    count(*) AS observed_value,
    CASE WHEN count(*) = 0 THEN 'pass' ELSE 'warn' END AS status,
    'exercises with muscle_group Unmapped: warn > 0' AS threshold
FROM core.dim_exercise
WHERE muscle_group = 'Unmapped';
