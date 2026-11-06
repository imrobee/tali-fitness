-- Demo setup (app/demo/setup.py): does this login role exist yet?
SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = CAST(:role AS text))
