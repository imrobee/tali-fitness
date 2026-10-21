-- Before re-parsing an activity, clear its open quarantine rows; the parse writes them
-- again if the lines are still unknown. Resolved rows are kept as history.
DELETE FROM ops.quarantine
WHERE source = :source
  AND entity_id = :entity_id
  AND resolved_at IS NULL;
