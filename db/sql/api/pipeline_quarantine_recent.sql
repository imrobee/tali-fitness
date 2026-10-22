-- The 20 most recent open quarantine rows, with a short snippet of the raw content.
SELECT source, entity_id, line_no, reason_code, left(raw_content, 200) AS raw_snippet,
       first_seen_at
FROM ops.quarantine
WHERE resolved_at IS NULL
ORDER BY first_seen_at DESC, id DESC
LIMIT 20;
