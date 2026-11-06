-- Demo setup: make the administrator a member of the demo writer, so it may create a
-- database owned by the writer (Postgres 16 needs SET for CREATE DATABASE ... OWNER) and
-- drop it again on the next setup (DROP DATABASE needs the owner's rights: INHERIT). A
-- superuser (as on this Mac) passes anyway; Neon's owner role is not one (D134). The
-- administrator owns everything else already, so the writer's rights add nothing to it.
-- Granting it again is a no-op.
SELECT format('GRANT %I TO CURRENT_USER WITH SET TRUE, INHERIT TRUE', CAST(:role AS text))
