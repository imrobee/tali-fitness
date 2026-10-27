-- The vacation the Me page edits: the one still running or still to come.
SELECT id, start_date, end_date
FROM app.vacation
WHERE end_date >= :today
ORDER BY start_date
LIMIT 1;
