-- Demo setup: the demo writer owns the demo database, and nothing else.
SELECT format('CREATE DATABASE %I OWNER %I', CAST(:database AS text), CAST(:owner AS text))
