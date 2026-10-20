-- Runs once, when the Postgres volume is first created.
-- POSTGRES_DB already creates the warehouse database "app". Airflow keeps its
-- metadata in its own database so the two never mix (ARCHITECTURE.md section 2).
CREATE DATABASE airflow;
