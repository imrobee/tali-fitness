"""Weekly and monthly trends, and the 7-day rolling average (ARCHITECTURE.md 5.5).

All of them take p_today, so tests control the clock. Each period is compared with the one
before it using LAG; one extra, hidden period is computed first so the oldest period shown
still has something to compare with.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-22
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The last p_count weeks (Monday to Sunday) or calendar months, oldest first, ending
    # with the one that contains p_today. Postgres weeks start on Monday, like dim_date.
    op.execute(
        """
        CREATE FUNCTION mart.fn_periods(p_today date, p_grain text, p_count integer)
        RETURNS TABLE (period_start date, period_end date)
        LANGUAGE sql STABLE AS $$
            SELECT
                g::date,
                (g + ('1 ' || p_grain)::interval - interval '1 day')::date
            FROM generate_series(
                date_trunc(p_grain, p_today::timestamp)
                    - (p_count - 1) * ('1 ' || p_grain)::interval,
                date_trunc(p_grain, p_today::timestamp),
                ('1 ' || p_grain)::interval
            ) AS g
            WHERE p_grain IN ('week', 'month')
            ORDER BY g
        $$
        """
    )

    # Training per period: sessions, active time, running distance, lifting volume, and
    # the change in active time against the period before (LAG).
    op.execute(
        """
        CREATE FUNCTION mart.fn_training_trend(p_today date, p_grain text, p_periods integer)
        RETURNS TABLE (
            period_start      date,
            period_end        date,
            is_current        boolean,
            sessions          integer,
            active_s          bigint,
            run_m             numeric,
            volume_kg         numeric,
            prev_sessions     integer,
            prev_active_s     bigint,
            active_change_pct integer
        )
        LANGUAGE sql STABLE AS $$
            WITH periods AS (
                SELECT * FROM mart.fn_periods(p_today, p_grain, p_periods + 1)
            ),
            activity AS (
                SELECT
                    dd.date AS day,
                    a.duration_s,
                    CASE WHEN t.app_type = 'run' THEN a.distance_m END AS run_m,
                    (SELECT coalesce(sum(s.volume_kg), 0) FROM core.fact_set s
                      WHERE s.activity_key = a.activity_key) AS volume_kg
                FROM core.fact_activity a
                JOIN core.dim_date dd USING (date_key)
                JOIN core.dim_activity_type t USING (activity_type_key)
                WHERE dd.date <= p_today
            ),
            totals AS (
                SELECT
                    p.period_start,
                    p.period_end,
                    count(a.day)::integer               AS sessions,
                    coalesce(sum(a.duration_s), 0)::bigint AS active_s,
                    coalesce(sum(a.run_m), 0)           AS run_m,
                    coalesce(sum(a.volume_kg), 0)       AS volume_kg
                FROM periods p
                LEFT JOIN activity a ON a.day BETWEEN p.period_start AND p.period_end
                GROUP BY p.period_start, p.period_end
            ),
            compared AS (
                SELECT
                    totals.*,
                    LAG(sessions) OVER w AS prev_sessions,
                    LAG(active_s) OVER w AS prev_active_s
                FROM totals
                WINDOW w AS (ORDER BY period_start)
            )
            SELECT
                c.period_start,
                c.period_end,
                p_today BETWEEN c.period_start AND c.period_end,
                c.sessions,
                c.active_s,
                c.run_m,
                c.volume_kg,
                c.prev_sessions,
                c.prev_active_s,
                -- NULLIF: no change can be stated against a period with no training.
                round(100.0 * (c.active_s - c.prev_active_s) / NULLIF(c.prev_active_s, 0))::integer
            FROM compared c
            WHERE c.period_start > (SELECT min(period_start) FROM periods)  -- drop the hidden one
            ORDER BY c.period_start
        $$
        """
    )

    # Nutrition per period. Averages are over logged days only: a day with no food logged
    # is missing data, not a day of eating 0 kcal (AVG skips NULLs).
    op.execute(
        """
        CREATE FUNCTION mart.fn_nutrition_trend(p_today date, p_grain text, p_periods integer)
        RETURNS TABLE (
            period_start  date,
            period_end    date,
            is_current    boolean,
            days_logged   integer,
            avg_kcal      numeric,
            avg_protein_g numeric,
            avg_budget    numeric,
            days_within   integer,
            days_over     integer,
            status        text,
            prev_avg_kcal numeric
        )
        LANGUAGE sql STABLE AS $$
            WITH periods AS (
                SELECT * FROM mart.fn_periods(p_today, p_grain, p_periods + 1)
            ),
            daily AS (
                SELECT *
                FROM mart.fn_daily_nutrition((SELECT min(period_start) FROM periods), p_today)
            ),
            totals AS (
                SELECT
                    p.period_start,
                    p.period_end,
                    count(d.kcal)::integer AS days_logged,
                    avg(d.kcal)            AS avg_kcal,
                    avg(d.protein_g)       AS avg_protein_g,
                    avg(d.calorie_budget) FILTER (WHERE d.kcal IS NOT NULL) AS avg_budget,
                    count(*) FILTER (WHERE d.calorie_status = 'within')::integer AS days_within,
                    count(*) FILTER (WHERE d.calorie_status = 'over')::integer   AS days_over
                FROM periods p
                LEFT JOIN daily d ON d.day BETWEEN p.period_start AND p.period_end
                GROUP BY p.period_start, p.period_end
            ),
            compared AS (
                SELECT totals.*, LAG(avg_kcal) OVER (ORDER BY period_start) AS prev_avg_kcal
                FROM totals
            )
            SELECT
                c.period_start,
                c.period_end,
                p_today BETWEEN c.period_start AND c.period_end,
                c.days_logged,
                round(c.avg_kcal),
                round(c.avg_protein_g),
                round(c.avg_budget),
                c.days_within,
                c.days_over,
                CASE
                    WHEN c.days_logged = 0          THEN 'not_logged'
                    WHEN c.avg_budget IS NULL       THEN 'not_set'
                    WHEN c.avg_kcal <= c.avg_budget THEN 'within'
                    ELSE 'over'
                END,
                round(c.prev_avg_kcal)
            FROM compared c
            WHERE c.period_start > (SELECT min(period_start) FROM periods)
            ORDER BY c.period_start
        $$
        """
    )

    # The 7-day rolling average for each day from p_from to p_to: that day and the six
    # before it, over the days that were logged. It reads six extra days before p_from so
    # the first day's window is full.
    op.execute(
        """
        CREATE FUNCTION mart.fn_nutrition_rolling(p_from date, p_to date)
        RETURNS TABLE (
            day            date,
            kcal           numeric,
            kcal_avg_7d    numeric,
            protein_avg_7d numeric,
            days_logged_7d integer
        )
        LANGUAGE sql STABLE AS $$
            SELECT r.day, r.kcal, r.kcal_avg_7d, r.protein_avg_7d, r.days_logged_7d
            FROM (
                SELECT
                    n.day,
                    n.kcal,
                    round(avg(n.kcal) OVER w)      AS kcal_avg_7d,
                    round(avg(n.protein_g) OVER w) AS protein_avg_7d,
                    (count(n.kcal) OVER w)::integer AS days_logged_7d
                FROM mart.fn_daily_nutrition(p_from - 6, p_to) n
                -- One row per calendar day (fn_daily_nutrition fills gaps), so 6 rows back
                -- is exactly 6 days back.
                WINDOW w AS (ORDER BY n.day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
            ) r
            WHERE r.day >= p_from
            ORDER BY r.day
        $$
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
