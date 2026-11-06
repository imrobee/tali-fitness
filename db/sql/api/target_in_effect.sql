-- The target in effect on :day (app.target_on: the latest effective_from on or before
-- it, or a demo visitor's own value). No row when nothing is set.
SELECT th.effective_from, target.calorie_budget, target.protein_goal
FROM app.target_on(:day) AS target
LEFT JOIN LATERAL (
    SELECT effective_from FROM app.target_history
    WHERE effective_from <= :day
    ORDER BY effective_from DESC
    LIMIT 1
) AS th ON true
WHERE target.calorie_budget IS NOT NULL OR target.protein_goal IS NOT NULL;
