-- The weight goal in effect on :day (app.weight_goal_on). No row when none is set.
SELECT goal.goal_kg
FROM (SELECT app.weight_goal_on(:day) AS goal_kg) AS goal
WHERE goal.goal_kg IS NOT NULL;
