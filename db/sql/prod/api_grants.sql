-- Production setup (scripts/setup_prod_role.py, D115, D134), run as the owner of the
-- warehouse tables: the API's and the pipeline job's login reads and writes rows in the
-- data schemas, and nothing more. No CREATE on any schema, so no DDL: migrations run as
-- the owner. Default privileges cover tables and sequences a later migration adds.
-- CONNECT by name: the demo setup revokes it from PUBLIC on this database (D118), which
-- would lock this login out too.
SELECT format(
    'GRANT CONNECT ON DATABASE %2$I TO %1$I; '
    'GRANT USAGE ON SCHEMA raw, core, mart, ops, app TO %1$I; '
    'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA raw, core, mart, ops, app TO %1$I; '
    'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA raw, core, mart, ops, app TO %1$I; '
    'ALTER DEFAULT PRIVILEGES IN SCHEMA raw, core, mart, ops, app '
    'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %1$I; '
    'ALTER DEFAULT PRIVILEGES IN SCHEMA raw, core, mart, ops, app '
    'GRANT USAGE, SELECT ON SEQUENCES TO %1$I; '
    'REVOKE CREATE ON SCHEMA raw, core, mart, ops, app, public FROM %1$I',
    CAST(:role AS text),
    current_database()
)
