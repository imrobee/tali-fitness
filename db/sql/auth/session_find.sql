SELECT sub, last_seen_at, expires_at
FROM app.session
WHERE session_hash = :session_hash;
