INSERT INTO ops.dq_results (run_id, check_name, status, observed_value, threshold)
VALUES (:run_id, :check_name, :status, :observed_value, :threshold);
