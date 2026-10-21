INSERT INTO ops.dq_results (run_id, check_name, status, observed_value, threshold, checked_at)
VALUES (:run_id, :check_name, :status, :observed_value, :threshold, CAST(:at AS timestamptz))
