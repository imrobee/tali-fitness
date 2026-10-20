SELECT access_token, refresh_token, expires_at
FROM ops.oauth_tokens
WHERE provider = :provider;
