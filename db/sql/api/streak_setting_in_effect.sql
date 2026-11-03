-- Relaxed weekends in effect on :day (strict when never set).
SELECT COALESCE(
    (SELECT lenient_weekends FROM app.streak_settings_history
     WHERE effective_from <= :day ORDER BY effective_from DESC LIMIT 1),
    false
) AS lenient_weekends;
