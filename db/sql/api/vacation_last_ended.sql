SELECT start_date, end_date
FROM app.vacation
WHERE end_date < :today
ORDER BY end_date DESC
LIMIT 1;
