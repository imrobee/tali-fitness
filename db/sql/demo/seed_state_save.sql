-- seeded_at is the real time the rebuild finished (clock_timestamp), not now(), which is
-- when its transaction began.
INSERT INTO demo.seed_state (id, scenario, as_of, seeded_at, duration_ms, story)
VALUES (
    1, :scenario, CAST(:as_of AS timestamptz), clock_timestamp(), :duration_ms,
    CAST(:story AS jsonb)
)
ON CONFLICT (id) DO UPDATE
SET scenario    = EXCLUDED.scenario,
    as_of       = EXCLUDED.as_of,
    seeded_at   = EXCLUDED.seeded_at,
    duration_ms = EXCLUDED.duration_ms,
    story       = EXCLUDED.story
