INSERT INTO core.fact_body_mass (local_date, date_key, weight_kg, start_ts, batch_id, source)
VALUES (:day, :date_key, :kg, CAST(:start AS timestamptz), :batch_id, 'MyNetDiary')
