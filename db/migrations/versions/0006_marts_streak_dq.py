"""User-entered tables, business-rule functions (qualifying day, freeze, streak, daily
nutrition), and data-quality results (ARCHITECTURE.md sections 5.3, 5.5, 8, 9).

Every rule that depends on "today" is a function taking p_today, so tests control the clock.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-21
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Targets are never edited in place: a change inserts a row effective from that day,
    # so past days keep the budget that was in effect then.
    op.execute(
        """
        CREATE TABLE app.target_history (
            effective_from date        PRIMARY KEY,
            calorie_budget integer     NOT NULL CHECK (calorie_budget > 0),
            protein_goal   integer     NOT NULL CHECK (protein_goal >= 0),
            created_at     timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE app.recovery_day (
            day        date        PRIMARY KEY,
            note       text,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE ops.dq_results (
            id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            run_id         bigint      REFERENCES ops.pipeline_runs,
            check_name     text        NOT NULL,
            status         text        NOT NULL CHECK (status IN ('pass', 'warn', 'fail')),
            observed_value numeric,
            threshold      text        NOT NULL,
            checked_at     timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    # One row per day, from the first day with any data to p_today (ARCHITECTURE.md 8).
    # States, first match wins: qualifying > recovery (valid only if the previous day
    # qualified, or it is the first day) > today_pending > at_risk (yesterday) > missed.
    # island_id counts the missed days so far: days in the same island form one chain.
    op.execute(
        """
        CREATE FUNCTION mart.fn_day_status(p_today date)
        RETURNS TABLE (
            day             date,
            has_activity    boolean,
            has_calories    boolean,
            recovery_logged boolean,
            qualifying      boolean,
            state           text,
            island_id       bigint,
            freezes_left    integer
        )
        LANGUAGE sql STABLE AS $$
            WITH bounds AS (
                -- LEAST ignores NULLs: the earliest day that has any kind of data.
                SELECT LEAST(
                    (SELECT min(dd.date)
                     FROM core.fact_activity fa JOIN core.dim_date dd USING (date_key)),
                    (SELECT min(local_date)
                     FROM core.fact_dietary_sample WHERE sample_type = 'energy'),
                    (SELECT min(rd.day) FROM app.recovery_day rd)
                ) AS first_day
            ),
            days AS (
                SELECT g::date AS d
                FROM bounds, generate_series(bounds.first_day, p_today, interval '1 day') AS g
                WHERE bounds.first_day IS NOT NULL
            ),
            flags AS (
                SELECT
                    days.d,
                    EXISTS (SELECT 1 FROM core.fact_activity fa
                            WHERE fa.date_key = to_char(days.d, 'YYYYMMDD')::int)
                        AS has_activity,
                    EXISTS (SELECT 1 FROM core.fact_dietary_sample s
                            WHERE s.local_date = days.d AND s.sample_type = 'energy')
                        AS has_calories,
                    EXISTS (SELECT 1 FROM app.recovery_day rd WHERE rd.day = days.d)
                        AS recovery_logged
                FROM days
            ),
            q AS (
                SELECT
                    flags.*,
                    has_activity AND has_calories AS qualifying,
                    -- NULL on the first day, which counts as "previous day qualified".
                    LAG(has_activity AND has_calories) OVER (ORDER BY flags.d) AS prev_qualifying
                FROM flags
            ),
            st AS (
                SELECT
                    q.*,
                    CASE
                        WHEN qualifying THEN 'qualifying'
                        WHEN recovery_logged AND COALESCE(prev_qualifying, true) THEN 'recovery'
                        WHEN q.d = p_today THEN 'today_pending'
                        WHEN q.d = p_today - 1 THEN 'at_risk'
                        ELSE 'missed'
                    END AS day_state
                FROM q
            )
            SELECT
                st.d,
                st.has_activity,
                st.has_calories,
                st.recovery_logged,
                st.qualifying,
                st.day_state,
                SUM((st.day_state = 'missed')::int) OVER (ORDER BY st.d),
                CASE
                    WHEN st.qualifying                      THEN 1  -- the freeze is released
                    WHEN st.day_state = 'recovery'          THEN 0  -- the freeze is in use
                    WHEN COALESCE(st.prev_qualifying, true) THEN 1
                    ELSE 0
                END
            FROM st
            ORDER BY st.d
        $$
        """
    )

    # The current streak: qualifying days in the chain (island) that contains p_today.
    # at_risk: yesterday is not logged yet, but the chain still has something to protect.
    op.execute(
        """
        CREATE FUNCTION mart.fn_streak(p_today date)
        RETURNS TABLE (streak integer, at_risk boolean, freezes_left integer)
        LANGUAGE sql STABLE AS $$
            WITH days AS (SELECT * FROM mart.fn_day_status(p_today)),
            current_chain AS (
                SELECT d2.* FROM days d2
                WHERE d2.island_id = (SELECT d1.island_id FROM days d1 WHERE d1.day = p_today)
            )
            SELECT
                (SELECT count(*) FROM current_chain WHERE current_chain.qualifying)::int,
                COALESCE(
                    (SELECT d3.state = 'at_risk' FROM days d3 WHERE d3.day = p_today - 1), false
                ) AND EXISTS (SELECT 1 FROM current_chain WHERE current_chain.qualifying),
                COALESCE((SELECT d4.freezes_left FROM days d4 WHERE d4.day = p_today), 1)
        $$
        """
    )

    # Calories and protein per day with the target in effect that day (the latest
    # effective_from on or before it). A function over a date range, so days without
    # any samples still appear, as 'not_logged'.
    op.execute(
        """
        CREATE FUNCTION mart.fn_daily_nutrition(p_from date, p_to date)
        RETURNS TABLE (
            day            date,
            kcal           numeric,
            protein_g      numeric,
            calorie_budget integer,
            protein_goal   integer,
            calorie_status text
        )
        LANGUAGE sql STABLE AS $$
            SELECT
                dd.date,
                energy.kcal,
                protein.grams,
                target.calorie_budget,
                target.protein_goal,
                CASE
                    WHEN energy.kcal IS NULL                  THEN 'not_logged'
                    WHEN target.calorie_budget IS NULL        THEN 'not_set'
                    WHEN energy.kcal <= target.calorie_budget THEN 'within'
                    ELSE 'over'
                END
            FROM core.dim_date dd
            LEFT JOIN (
                SELECT local_date, sum(value) AS kcal
                FROM core.fact_dietary_sample WHERE sample_type = 'energy' GROUP BY local_date
            ) AS energy ON energy.local_date = dd.date
            LEFT JOIN (
                SELECT local_date, sum(value) AS grams
                FROM core.fact_dietary_sample WHERE sample_type = 'protein' GROUP BY local_date
            ) AS protein ON protein.local_date = dd.date
            LEFT JOIN LATERAL (
                SELECT th.calorie_budget, th.protein_goal
                FROM app.target_history th
                WHERE th.effective_from <= dd.date
                ORDER BY th.effective_from DESC
                LIMIT 1
            ) AS target ON true
            WHERE dd.date BETWEEN p_from AND p_to
            ORDER BY dd.date
        $$
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
