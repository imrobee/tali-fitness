-- A new weight goal applies from today; saving twice on the same day replaces that row.
INSERT INTO app.weight_goal_history (effective_from, goal_kg)
VALUES (:today, :goal_kg)
ON CONFLICT (effective_from) DO UPDATE
SET goal_kg = EXCLUDED.goal_kg,
    created_at = now();
