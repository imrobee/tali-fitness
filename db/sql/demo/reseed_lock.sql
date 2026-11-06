-- One rebuild at a time: a lock that lasts until this transaction ends (commit or
-- rollback), so it can never be left behind. False when another rebuild holds it.
-- Transaction-level, not session-level: Neon's pooler (PgBouncer, transaction mode)
-- does not support session-level advisory locks.
SELECT pg_try_advisory_xact_lock(hashtext('fitness-tracker demo reseed'))
