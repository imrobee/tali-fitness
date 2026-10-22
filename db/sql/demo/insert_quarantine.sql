INSERT INTO ops.quarantine (source, entity_id, line_no, raw_content, reason_code, first_seen_at)
VALUES ('strava', :entity_id, :line_no, :raw_content, 'unparsed_line', CAST(:at AS timestamptz))
