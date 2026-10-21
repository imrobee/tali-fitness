"""Health ingest: date dimension, raw batches and samples, dietary fact, quarantine,
and the function that applies a batch to core (ARCHITECTURE.md sections 5 and 6.2).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-20
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One row per calendar day, 2020-01-01 to 2035-12-31. Built here (not Slice 4)
    # because fact_dietary_sample references it.
    op.execute(
        """
        CREATE TABLE core.dim_date (
            date_key    integer PRIMARY KEY,          -- YYYYMMDD, e.g. 20261020
            date        date    NOT NULL UNIQUE,
            iso_year    integer NOT NULL,
            iso_week    integer NOT NULL,
            week_start  date    NOT NULL,             -- Monday of the ISO week
            month_start date    NOT NULL,
            dow         integer NOT NULL CHECK (dow BETWEEN 1 AND 7),  -- 1 = Monday
            is_weekend  boolean NOT NULL
        )
        """
    )
    op.execute(
        """
        INSERT INTO core.dim_date
        SELECT
            (EXTRACT(YEAR FROM d) * 10000 + EXTRACT(MONTH FROM d) * 100 + EXTRACT(DAY FROM d))::int,
            d,
            EXTRACT(ISOYEAR FROM d)::int,
            EXTRACT(WEEK FROM d)::int,
            (d - (EXTRACT(ISODOW FROM d)::int - 1))::date,
            date_trunc('month', d)::date,
            EXTRACT(ISODOW FROM d)::int,
            EXTRACT(ISODOW FROM d) IN (6, 7)
        FROM (
            SELECT day::date AS d
            FROM generate_series(DATE '2020-01-01', DATE '2035-12-31', INTERVAL '1 day') AS day
        ) AS days
        """
    )

    # One row per accepted Shortcut POST. payload is the full body exactly as received.
    op.execute(
        """
        CREATE TABLE raw.health_batches (
            batch_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
            received_at    timestamptz NOT NULL DEFAULT now(),
            window_start   date        NOT NULL,
            window_end     date        NOT NULL,
            device_tz      text        NOT NULL,
            payload_sha256 text        NOT NULL,
            payload        jsonb       NOT NULL,
            applied_at     timestamptz,
            CHECK (window_end >= window_start)
        )
        """
    )
    op.execute(
        "CREATE INDEX health_batches_window_idx "
        "ON raw.health_batches (window_start, window_end, received_at)"
    )

    # One row per accepted sample, value and unit as received (kJ stays kJ).
    op.execute(
        """
        CREATE TABLE raw.health_samples (
            batch_id   uuid        NOT NULL REFERENCES raw.health_batches ON DELETE CASCADE,
            idx        integer     NOT NULL,      -- position in the batch's samples list
            type       text        NOT NULL
                CHECK (type IN ('dietary_energy', 'dietary_protein', 'body_mass')),
            value      numeric     NOT NULL,
            unit       text        NOT NULL,
            start_ts   timestamptz NOT NULL,
            local_date date        NOT NULL,      -- from the sample's own offset, computed once
            source     text,
            PRIMARY KEY (batch_id, idx),
            CHECK (
                (type = 'dietary_energy' AND unit IN ('kcal', 'kJ'))
                OR (type = 'dietary_protein' AND unit = 'g')
                OR (type = 'body_mass' AND unit = 'kg')
            ),
            CHECK (type <> 'body_mass' OR value BETWEEN 30 AND 250)
        )
        """
    )

    # Dietary samples in the star schema, energy always in kcal.
    op.execute(
        """
        CREATE TABLE core.fact_dietary_sample (
            sample_key  bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            batch_id    uuid        NOT NULL REFERENCES raw.health_batches,
            sample_idx  integer     NOT NULL,
            date_key    integer     NOT NULL REFERENCES core.dim_date,
            local_date  date        NOT NULL,
            sample_type text        NOT NULL CHECK (sample_type IN ('energy', 'protein')),
            value       numeric     NOT NULL,     -- kcal for energy, grams for protein
            start_ts    timestamptz NOT NULL,
            source      text,
            UNIQUE (batch_id, sample_idx),
            CHECK (
                date_key = (EXTRACT(YEAR FROM local_date) * 10000
                            + EXTRACT(MONTH FROM local_date) * 100
                            + EXTRACT(DAY FROM local_date))::int
            ),
            CHECK (sample_type <> 'energy' OR (value > 0 AND value <= 5000)),
            CHECK (sample_type <> 'protein' OR (value >= 0 AND value <= 500))
        )
        """
    )
    op.execute(
        "CREATE INDEX fact_dietary_sample_day_idx "
        "ON core.fact_dietary_sample (local_date, sample_type)"
    )

    # Rejected records from any source, kept with the raw content and a reason.
    op.execute(
        """
        CREATE TABLE ops.quarantine (
            id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source        text        NOT NULL,   -- 'health' or 'strava'
            entity_id     text        NOT NULL,   -- batch_id or strava_id
            line_no       integer,                -- sample index or description line
            raw_content   text        NOT NULL,
            reason_code   text        NOT NULL CHECK (reason_code IN (
                'invalid_sample', 'unknown_type', 'bad_unit', 'out_of_range',
                'outside_window', 'bad_timestamp', 'unparsed_line', 'empty_exercise')),
            error         text,
            first_seen_at timestamptz NOT NULL DEFAULT now(),
            resolved_at   timestamptz
        )
        """
    )

    # Applies one batch to core: replace only the (local_date, sample_type) pairs that
    # have samples in this batch (DECISIONS D1), converting kJ to kcal on the way.
    op.execute(
        """
        CREATE FUNCTION core.apply_health_batch(p_batch_id uuid) RETURNS void
        LANGUAGE sql AS $$
            WITH batch_samples AS (
                SELECT idx, local_date, value, unit, start_ts, source,
                       CASE type WHEN 'dietary_energy' THEN 'energy'
                                 WHEN 'dietary_protein' THEN 'protein' END AS sample_type
                FROM raw.health_samples
                WHERE batch_id = p_batch_id
                  AND type IN ('dietary_energy', 'dietary_protein')
            )
            DELETE FROM core.fact_dietary_sample f
            USING (SELECT DISTINCT local_date, sample_type FROM batch_samples) pairs
            WHERE f.local_date = pairs.local_date
              AND f.sample_type = pairs.sample_type;

            INSERT INTO core.fact_dietary_sample
                (batch_id, sample_idx, date_key, local_date, sample_type, value, start_ts, source)
            SELECT p_batch_id,
                   s.idx,
                   d.date_key,
                   s.local_date,
                   CASE s.type WHEN 'dietary_energy' THEN 'energy' ELSE 'protein' END,
                   CASE WHEN s.unit = 'kJ' THEN s.value * 0.239006 ELSE s.value END,
                   s.start_ts,
                   s.source
            FROM raw.health_samples s
            JOIN core.dim_date d ON d.date = s.local_date
            WHERE s.batch_id = p_batch_id
              AND s.type IN ('dietary_energy', 'dietary_protein');

            UPDATE raw.health_batches SET applied_at = now() WHERE batch_id = p_batch_id;
        $$
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
