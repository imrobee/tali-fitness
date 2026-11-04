UPDATE app.session
SET last_seen_at = :now
WHERE session_hash = :session_hash;
