-- Replace the batch's (local_date, sample_type) pairs in core (migration 0004).
SELECT core.apply_health_batch(:batch_id);
