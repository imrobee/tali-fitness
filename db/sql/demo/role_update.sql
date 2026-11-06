-- Demo setup: a fresh password for a demo role that already exists. Only the password: a
-- role that isn't a superuser (Neon's owner) may not even mention SUPERUSER in ALTER ROLE,
-- so the rights set at CREATE are checked afterwards instead (demo/role_is_plain.sql).
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', CAST(:role AS text), CAST(:password AS text))
