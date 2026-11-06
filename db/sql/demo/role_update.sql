-- Demo setup: the same rights and a fresh password for a demo role that already exists.
SELECT format(
    'ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT',
    CAST(:role AS text), CAST(:password AS text)
)
