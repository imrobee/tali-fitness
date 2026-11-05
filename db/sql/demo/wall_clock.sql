-- The database's real time before a replayed step; every row the step writes with now()
-- is at or after it.
SELECT clock_timestamp()
