INSERT INTO app.session (session_hash, sub, created_at, last_seen_at, expires_at)
VALUES (:session_hash, :sub, :now, :now, :expires_at);
