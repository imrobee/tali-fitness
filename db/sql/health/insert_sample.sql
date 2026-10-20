INSERT INTO raw.health_samples
    (batch_id, idx, type, value, unit, start_ts, local_date, source)
VALUES
    (:batch_id, :idx, :type, :value, :unit, :start_ts, :local_date, :source);
