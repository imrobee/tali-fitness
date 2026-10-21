INSERT INTO core.fact_dietary_sample (
    batch_id, sample_idx, date_key, local_date, sample_type, value, start_ts
)
VALUES (:batch_id, :idx, :date_key, :day, :type, :value, CAST(:start AS timestamptz))
