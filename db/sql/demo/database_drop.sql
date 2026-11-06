-- Demo setup: FORCE ends the demo API's open connections.
SELECT format('DROP DATABASE IF EXISTS %I WITH (FORCE)', CAST(:database AS text))
