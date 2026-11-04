-- Past their absolute lifetime, or idle for longer than SESSION_IDLE_DAYS.
DELETE FROM app.session
WHERE expires_at <= :now
   OR last_seen_at <= :idle_cutoff;
