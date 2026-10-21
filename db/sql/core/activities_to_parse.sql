-- Activities never parsed, re-fetched since their last parse (the raw version differs
-- from the one parsed), or parsed by an older grammar (bumping PARSER_VERSION replays
-- every activity from raw).
SELECT activity_key, strava_id, date_key, description_raw
FROM core.fact_activity
WHERE parsed_fetched_at IS DISTINCT FROM source_fetched_at
   OR parser_version IS DISTINCT FROM :parser_version
ORDER BY started_at;
