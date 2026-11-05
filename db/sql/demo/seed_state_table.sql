-- One row: when the demo was last rebuilt, as of which moment, and how long it took.
-- The Data and sync panel shows it; a demo visit asks for a rebuild when it is over a
-- day old (app/demo/self_heal.py).
CREATE TABLE IF NOT EXISTS demo.seed_state (
    id          integer PRIMARY KEY CHECK (id = 1),
    scenario    text NOT NULL,
    as_of       timestamptz NOT NULL,
    seeded_at   timestamptz NOT NULL,
    duration_ms integer NOT NULL CHECK (duration_ms >= 0)
)
