"""Settings in effect on a day, through one function each, so a demo visitor's own
settings can apply for a single request (docs/DECISIONS.md D122).

The rules do not change for the real app: a target still applies from the day it was
set, and past days keep their old targets. Only the lookups move into app.target_on,
app.weight_goal_on and app.lenient_weekends_on; the three mart functions that did those
lookups inline are re-created to call them, otherwise word for word.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-05
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        -- A demo visitor's own setting for this request, or NULL. The demo API sets
        -- demo.<name> with set_config(..., true): it lasts until the end of the current
        -- transaction only, so it can never reach another request or visitor, pooled
        -- connection or not. The real app never sets it, so this is always NULL there.
        CREATE FUNCTION app.demo_setting(p_name text) RETURNS text
        LANGUAGE sql STABLE AS $$
            SELECT nullif(current_setting('demo.' || p_name, true), '')
        $$;

        -- The calorie budget and protein goal in effect on a day: the latest target set on
        -- or before it (targets apply from the day they are set), unless the demo visitor
        -- set their own, which then applies to every day. One row, NULLs when unset.
        CREATE FUNCTION app.target_on(p_day date)
        RETURNS TABLE (calorie_budget integer, protein_goal integer)
        LANGUAGE sql STABLE AS $$
            SELECT
                COALESCE(app.demo_setting('calorie_budget')::integer, th.calorie_budget),
                COALESCE(app.demo_setting('protein_goal')::integer, th.protein_goal)
            FROM (SELECT 1) AS one
            LEFT JOIN LATERAL (
                SELECT calorie_budget, protein_goal
                FROM app.target_history
                WHERE effective_from <= p_day
                ORDER BY effective_from DESC
                LIMIT 1
            ) AS th ON true
        $$;

        CREATE FUNCTION app.weight_goal_on(p_day date) RETURNS numeric
        LANGUAGE sql STABLE AS $$
            SELECT COALESCE(
                app.demo_setting('weight_goal_kg')::numeric,
                (SELECT goal_kg FROM app.weight_goal_history
                 WHERE effective_from <= p_day ORDER BY effective_from DESC LIMIT 1)
            )
        $$;

        -- Relaxed weekends in effect on a day (strict when never set).
        CREATE FUNCTION app.lenient_weekends_on(p_day date) RETURNS boolean
        LANGUAGE sql STABLE AS $$
            SELECT COALESCE(
                app.demo_setting('lenient_weekends')::boolean,
                (SELECT lenient_weekends FROM app.streak_settings_history
                 WHERE effective_from <= p_day ORDER BY effective_from DESC LIMIT 1),
                false
            )
        $$;
        """
    )
    # Same signatures, so CREATE OR REPLACE keeps everything that calls them.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mart.fn_daily_nutrition(p_from date, p_to date)
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
            -- The target in effect that day (a demo visitor's own value wins, D122).
            CROSS JOIN LATERAL app.target_on(dd.date) AS target
            WHERE dd.date BETWEEN p_from AND p_to
            ORDER BY dd.date
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mart.fn_weight_trend(p_from date, p_to date)
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
            -- The goal in effect that day (a demo visitor's own value wins, D122).
            CROSS JOIN LATERAL (SELECT app.weight_goal_on(wc.day) AS goal_kg) AS goal
            WHERE wc.day >= p_from
            ORDER BY wc.day
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mart.fn_day_status(p_today date)
        RETURNS TABLE (
            day             date,
            has_activity    boolean,
            has_calories    boolean,
            recovery_logged boolean,
            calorie_status  text,
            kind            text,
            lenient         boolean,
            breaks          boolean,
            state           text,
            counted         boolean,
            island_id       bigint
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
                SELECT n.day, n.calorie_status
                FROM bounds, mart.fn_daily_nutrition(bounds.first_day, p_today) n
                WHERE bounds.first_day IS NOT NULL
            ),
            flags AS (
                SELECT
                    days.day,
                    days.calorie_status,
                    EXISTS (SELECT 1 FROM core.fact_activity fa
                            WHERE fa.date_key = to_char(days.day, 'YYYYMMDD')::int)
                        AS has_activity,
                    days.calorie_status <> 'not_logged' AS has_calories,
                    EXISTS (SELECT 1 FROM app.recovery_day rd WHERE rd.day = days.day)
                        AS recovery_logged,
                    EXISTS (SELECT 1 FROM app.vacation v
                            WHERE days.day BETWEEN v.start_date AND v.end_date)
                    OR (
                        EXTRACT(ISODOW FROM days.day) IN (6, 7)
                        AND app.lenient_weekends_on(days.day)
                    ) AS lenient
                FROM days
            ),
            kinds AS (
                SELECT
                    flags.*,
                    CASE
                        WHEN recovery_logged                THEN 'recovery'
                        WHEN calorie_status = 'over'        THEN 'over'
                        WHEN has_calories AND has_activity  THEN 'success'
                        WHEN has_calories OR has_activity   THEN 'recovery'
                        ELSE 'miss'
                    END AS kind
                FROM flags
            ),
            paired AS (
                SELECT
                    kinds.*,
                    LAG(kind) OVER w    AS prev_kind,
                    LAG(lenient) OVER w AS prev_lenient
                FROM kinds
                WINDOW w AS (ORDER BY day)
            ),
            judged AS (
                SELECT
                    paired.*,
                    CASE
                        WHEN kind = 'miss' THEN true
                        WHEN lenient       THEN false
                        WHEN kind IN ('over', 'recovery')
                             AND kind = prev_kind
                             AND NOT prev_lenient THEN true
                        ELSE false  -- also the first day: prev_kind is NULL
                    END AS breaks
                FROM paired
            ),
            st AS (
                SELECT
                    judged.*,
                    CASE
                        WHEN NOT breaks            THEN 'counted'
                        WHEN judged.day = p_today     THEN 'pending'
                        WHEN judged.day = p_today - 1 THEN 'at_risk'
                        ELSE 'broken'
                    END AS state
                FROM judged
            )
            SELECT
                st.day,
                st.has_activity,
                st.has_calories,
                st.recovery_logged,
                st.calorie_status,
                st.kind,
                st.lenient,
                st.breaks,
                st.state,
                st.state = 'counted',
                SUM((st.state = 'broken')::int) OVER (ORDER BY st.day)
            FROM st
            ORDER BY st.day
        $$
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
