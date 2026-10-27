-- A weekend setting applies from today; past weekends keep theirs. Same day: replaced.
INSERT INTO app.streak_settings_history (effective_from, lenient_weekends)
VALUES (:today, :lenient_weekends)
ON CONFLICT (effective_from) DO UPDATE
SET lenient_weekends = EXCLUDED.lenient_weekends,
    created_at = now();
