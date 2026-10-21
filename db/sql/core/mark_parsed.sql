UPDATE core.fact_activity
SET parse_status      = :parse_status,
    parsed_fetched_at = source_fetched_at,  -- the raw version just parsed
    parsed_at         = now(),
    parser_version    = :parser_version
WHERE activity_key = :activity_key;
