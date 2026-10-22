-- The weight goal in effect on :day: the latest effective_from on or before it.
SELECT goal_kg
FROM app.weight_goal_history
WHERE effective_from <= :day
ORDER BY effective_from DESC
LIMIT 1;
