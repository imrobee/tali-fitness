-- Demo setup: builds the statement that creates a demo login role. DDL cannot take bind
-- parameters, so format() quotes the name (%I) and password (%L) inside the server.
-- No superuser, database or role rights: a demo role can do only what it is granted.
SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT',
    CAST(:role AS text), CAST(:password AS text)
)
