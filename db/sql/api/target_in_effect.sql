-- The target in effect on :day: the latest effective_from on or before it.
SELECT effective_from, calorie_budget, protein_goal
FROM app.target_history
WHERE effective_from <= :day
ORDER BY effective_from DESC
LIMIT 1;
