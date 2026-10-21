INSERT INTO app.recovery_day (day, note) VALUES (:day, :note)
ON CONFLICT (day) DO NOTHING;
