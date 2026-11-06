-- Relaxed weekends in effect on :day (strict when never set; app.lenient_weekends_on).
SELECT app.lenient_weekends_on(:day) AS lenient_weekends;
