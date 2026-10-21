SELECT exercise_key
FROM core.dim_exercise
WHERE exercise_name = :exercise_name
  AND equipment IS NOT DISTINCT FROM CAST(:equipment AS text);
