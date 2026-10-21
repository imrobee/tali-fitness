-- New targets apply from today; past days keep theirs. Saving twice on the same day
-- replaces that day's row.
INSERT INTO app.target_history (effective_from, calorie_budget, protein_goal)
VALUES (:today, :calorie_budget, :protein_goal)
ON CONFLICT (effective_from) DO UPDATE
SET calorie_budget = EXCLUDED.calorie_budget,
    protein_goal   = EXCLUDED.protein_goal,
    created_at     = now();
