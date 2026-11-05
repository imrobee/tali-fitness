-- Demo setup, run as the demo writer (the owner of every demo table): the reader may read
-- the data schemas and nothing else. Default privileges cover tables a later migration
-- adds. Never the token or session tables, even though they are empty in the demo.
SELECT format(
    'GRANT USAGE ON SCHEMA raw, core, mart, ops, app, demo TO %1$I; '
    'GRANT SELECT ON ALL TABLES IN SCHEMA raw, core, mart, ops, app, demo TO %1$I; '
    'ALTER DEFAULT PRIVILEGES IN SCHEMA raw, core, mart, ops, app, demo GRANT SELECT ON TABLES TO %1$I; '
    'REVOKE ALL ON ops.oauth_tokens, app.session FROM %1$I',
    CAST(:role AS text)
)
