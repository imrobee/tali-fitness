"""Body mass in core, the weight goal history, and the weight trend (ARCHITECTURE.md 5.2,
5.3, 5.5, 14 #8).

One weight per local day, the last reading of that day. Applied in the same batch
replace as the calories and protein (DECISIONS D1): a batch replaces the days it has a
body_mass sample for, and leaves other days alone.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-22
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Goals are history like targets, but kept in their own table, so saving the calorie
    # budget never clears the weight goal.
    op.execute(
        """
        CREATE TABLE app.weight_goal_history (
            effective_from date         PRIMARY KEY,
            goal_kg        numeric(5,1) NOT NULL CHECK (goal_kg BETWEEN 30 AND 250),
            created_at     timestamptz  NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE core.fact_body_mass (
            local_date date        PRIMARY KEY,
            date_key   integer     NOT NULL REFERENCES core.dim_date,
            weight_kg  numeric     NOT NULL CHECK (weight_kg BETWEEN 30 AND 250),
            start_ts   timestamptz NOT NULL,
            batch_id   uuid        NOT NULL REFERENCES raw.health_batches,
            source     text
        )
        """
    )

    # Same function as migration 0004 for calories and protein, plus body mass: the days
    # with a body_mass sample in this batch are replaced by the day's last reading
    # (latest start, then the later position in the batch).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION core.apply_health_batch(p_batch_id uuid) RETURNS void
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

            DELETE FROM core.fact_body_mass b
            USING (SELECT DISTINCT local_date FROM raw.health_samples
                   WHERE batch_id = p_batch_id AND type = 'body_mass') days
            WHERE b.local_date = days.local_date;

            INSERT INTO core.fact_body_mass
                (local_date, date_key, weight_kg, start_ts, batch_id, source)
            SELECT DISTINCT ON (s.local_date)
                   s.local_date, d.date_key, s.value, s.start_ts, p_batch_id, s.source
            FROM raw.health_samples s
            JOIN core.dim_date d ON d.date = s.local_date
            WHERE s.batch_id = p_batch_id
              AND s.type = 'body_mass'
            ORDER BY s.local_date, s.start_ts DESC, s.idx DESC;

            UPDATE raw.health_batches SET applied_at = now() WHERE batch_id = p_batch_id;
        $$
        """
    )

    # One row per day from p_from to p_to, with a 7-day average of the logged weights, the
    # change in that average against 7 days earlier, and the goal in effect that day. The
    # query reads 13 days before p_from: 6 for the first average, 7 for the comparison.
    # Days with no weight show 'not_logged' and no average is invented for them.
    op.execute(
        """
        CREATE FUNCTION mart.fn_weight_trend(p_from date, p_to date)
        RETURNS TABLE (
            day            date,
            weight_kg      numeric,
            avg_7d_kg      numeric,
            change_7d_kg   numeric,
            goal_kg        numeric,
            status         text
        )
        LANGUAGE sql STABLE AS $$
            WITH days AS (
                SELECT dd.date AS day, b.weight_kg
                FROM core.dim_date dd
                LEFT JOIN core.fact_body_mass b ON b.local_date = dd.date
                WHERE dd.date BETWEEN p_from - 13 AND p_to
            ),
            rolling AS (
                SELECT
                    days.day,
                    days.weight_kg,
                    avg(days.weight_kg) OVER w AS avg_7d_kg
                FROM days
                WINDOW w AS (ORDER BY days.day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
            ),
            with_change AS (
                SELECT
                    rolling.*,
                    rolling.avg_7d_kg
                        - LAG(rolling.avg_7d_kg, 7) OVER (ORDER BY rolling.day) AS change_7d_kg
                FROM rolling
            )
            SELECT
                wc.day,
                wc.weight_kg,
                round(wc.avg_7d_kg, 2),
                round(wc.change_7d_kg, 2),
                goal.goal_kg,
                CASE
                    WHEN wc.weight_kg IS NULL THEN 'not_logged'
                    WHEN goal.goal_kg IS NULL THEN 'not_set'
                    WHEN wc.weight_kg <= goal.goal_kg THEN 'at_or_below'
                    ELSE 'above'
                END
            FROM with_change wc
            LEFT JOIN LATERAL (
                SELECT g.goal_kg
                FROM app.weight_goal_history g
                WHERE g.effective_from <= wc.day
                ORDER BY g.effective_from DESC
                LIMIT 1
            ) AS goal ON true
            WHERE wc.day >= p_from
            ORDER BY wc.day
        $$
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
