-- Strava may return a new refresh token on every refresh and invalidates the old one,
-- so every response is saved in full.
INSERT INTO ops.oauth_tokens (provider, access_token, refresh_token, expires_at, scope, updated_at)
VALUES (:provider, :access_token, :refresh_token, :expires_at, :scope, now())
ON CONFLICT (provider) DO UPDATE
SET access_token  = EXCLUDED.access_token,
    refresh_token = EXCLUDED.refresh_token,
    expires_at    = EXCLUDED.expires_at,
    scope         = COALESCE(EXCLUDED.scope, ops.oauth_tokens.scope),
    updated_at    = now();
