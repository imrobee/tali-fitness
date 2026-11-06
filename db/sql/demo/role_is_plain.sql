-- Demo setup: true when a demo role has no special rights (as role_create.sql makes it):
-- no superuser, database or role creation, replication, RLS bypass or inherited rights.
SELECT NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolinherit)
FROM pg_roles
WHERE rolname = CAST(:role AS text)
