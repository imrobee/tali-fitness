-- Demo setup: nobody may connect to this database unless granted by name. Postgres lets
-- every role connect to every database by default (through PUBLIC); this removes that,
-- so the demo roles cannot even open the real warehouse. Owners and superusers keep
-- their access, so the real app and Airflow are unaffected.
SELECT format('REVOKE CONNECT, TEMPORARY ON DATABASE %I FROM PUBLIC', CAST(:database AS text))
