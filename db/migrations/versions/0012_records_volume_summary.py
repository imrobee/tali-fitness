"""Personal records by estimated 1RM, weekly volume per muscle group, and the weekly
summary against the week before (PROJECT_PLAN Slice 7b; ARCHITECTURE.md 5.5).

All take p_today, so tests control the clock.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-22
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Estimated 1RM per weighted set with the Epley formula, w * (1 + reps / 30), for 1 to
    # 12 reps (beyond that the estimate is not trustworthy). Per exercise: the best set
    # (RANK; a tie goes to the earlier set), and the best before it (a running MAX over the
    # earlier sets), so the page can say how much the record improved.
    op.execute(
        """
        CREATE FUNCTION mart.fn_personal_records(p_today date)
        RETURNS TABLE (
            exercise_key   integer,
            exercise_name  text,
            equipment      text,
            muscle_group   text,
            best_e1rm_kg   numeric,
            weight_kg      numeric,
            reps           integer,
            day            date,
            activity_key   bigint,
            prev_e1rm_kg   numeric,
            sessions       integer
        )
        LANGUAGE sql STABLE AS $$
            WITH sets AS (
                SELECT
                    s.set_key,
                    s.exercise_key,
                    s.activity_key,
                    s.weight_kg,
                    s.reps,
                    dd.date AS day,
                    s.weight_kg * (1 + s.reps / 30.0) AS e1rm
                FROM core.fact_set s
                JOIN core.dim_date dd ON dd.date_key = s.date_key
                WHERE s.set_kind = 'weight_reps'
                  AND s.reps BETWEEN 1 AND 12
                  AND s.weight_kg > 0
                  AND dd.date <= p_today
            ),
            ranked AS (
                SELECT
                    sets.*,
                    RANK() OVER (
                        PARTITION BY exercise_key ORDER BY e1rm DESC, day, set_key
                    ) AS best_rank,
                    MAX(e1rm) OVER (
                        PARTITION BY exercise_key ORDER BY day, set_key
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) AS best_before
                FROM sets
            ),
            -- Postgres has no count(DISTINCT ...) OVER, so sessions per exercise are grouped.
            sessions AS (
                SELECT exercise_key, count(DISTINCT activity_key)::integer AS sessions
                FROM sets
                GROUP BY exercise_key
            )
            SELECT
                r.exercise_key,
                e.exercise_name,
                e.equipment,
                e.muscle_group,
                round(r.e1rm, 2),
                r.weight_kg,
                r.reps,
                r.day,
                r.activity_key,
                round(r.best_before, 2),
                n.sessions
            FROM ranked r
            JOIN core.dim_exercise e USING (exercise_key)
            JOIN sessions n USING (exercise_key)
            WHERE r.best_rank = 1
            ORDER BY r.day DESC, e.exercise_name
        $$
        """
    )

    # Sets and volume per muscle group for each of the last p_weeks weeks, with the week
    # before by LAG. Every muscle group trained in the range gets a row in every week
    # (0 when not trained), so LAG compares like with like.
    op.execute(
        """
        CREATE FUNCTION mart.fn_muscle_volume(p_today date, p_weeks integer)
        RETURNS TABLE (
            week_start     date,
            week_end       date,
            muscle_group   text,
            sets           integer,
            volume_kg      numeric,
            prev_sets      integer,
            prev_volume_kg numeric
        )
        LANGUAGE sql STABLE AS $$
            WITH weeks AS (
                SELECT * FROM mart.fn_periods(p_today, 'week', p_weeks + 1)
            ),
            sets AS (
                SELECT dd.date AS day, e.muscle_group, s.volume_kg
                FROM core.fact_set s
                JOIN core.dim_date dd ON dd.date_key = s.date_key
                JOIN core.dim_exercise e USING (exercise_key)
                WHERE dd.date BETWEEN (SELECT min(period_start) FROM weeks) AND p_today
            ),
            groups AS (SELECT DISTINCT muscle_group FROM sets),
            totals AS (
                SELECT
                    w.period_start,
                    w.period_end,
                    g.muscle_group,
                    count(s.day)::integer          AS sets,
                    coalesce(sum(s.volume_kg), 0)  AS volume_kg
                FROM weeks w
                CROSS JOIN groups g
                LEFT JOIN sets s
                    ON s.muscle_group = g.muscle_group
                   AND s.day BETWEEN w.period_start AND w.period_end
                GROUP BY w.period_start, w.period_end, g.muscle_group
            ),
            compared AS (
                SELECT
                    totals.*,
                    LAG(sets) OVER w      AS prev_sets,
                    LAG(volume_kg) OVER w AS prev_volume_kg
                FROM totals
                WINDOW w AS (PARTITION BY muscle_group ORDER BY period_start)
            )
            SELECT period_start, period_end, muscle_group, sets, volume_kg,
                   prev_sets, prev_volume_kg
            FROM compared
            WHERE period_start > (SELECT min(period_start) FROM weeks)  -- drop the hidden week
            ORDER BY period_start, sets DESC, muscle_group
        $$
        """
    )

    # Last finished week (Monday to Sunday before p_today's week) against the week before:
    # training and nutrition from the trend functions, which already compare with LAG,
    # plus qualifying days and the average weight, compared here with LAG.
    op.execute(
        """
        CREATE FUNCTION mart.fn_weekly_summary(p_today date)
        RETURNS TABLE (
            week_start           date,
            week_end             date,
            qualifying_days      integer,
            prev_qualifying_days integer,
            sessions             integer,
            prev_sessions        integer,
            active_s             bigint,
            prev_active_s        bigint,
            run_m                numeric,
            volume_kg            numeric,
            days_logged          integer,
            avg_kcal             numeric,
            prev_avg_kcal        numeric,
            avg_protein_g        numeric,
            avg_weight_kg        numeric,
            prev_avg_weight_kg   numeric
        )
        LANGUAGE sql STABLE AS $$
            WITH last_sunday AS (
                SELECT (date_trunc('week', p_today::timestamp) - interval '1 day')::date AS d
            ),
            weeks AS (
                SELECT * FROM mart.fn_periods((SELECT d FROM last_sunday), 'week', 2)
            ),
            qualifying AS (
                SELECT w.period_start, count(*) FILTER (WHERE ds.qualifying)::integer AS days
                FROM weeks w
                LEFT JOIN mart.fn_day_status(p_today) ds
                    ON ds.day BETWEEN w.period_start AND w.period_end
                GROUP BY w.period_start
            ),
            weight AS (
                SELECT w.period_start, avg(b.weight_kg) AS avg_kg
                FROM weeks w
                LEFT JOIN core.fact_body_mass b
                    ON b.local_date BETWEEN w.period_start AND w.period_end
                GROUP BY w.period_start
            ),
            per_week AS (
                SELECT
                    w.period_start,
                    w.period_end,
                    q.days,
                    LAG(q.days) OVER (ORDER BY w.period_start)     AS prev_days,
                    wt.avg_kg,
                    LAG(wt.avg_kg) OVER (ORDER BY w.period_start)  AS prev_avg_kg
                FROM weeks w
                JOIN qualifying q USING (period_start)
                JOIN weight wt USING (period_start)
            ),
            training AS (
                SELECT * FROM mart.fn_training_trend((SELECT d FROM last_sunday), 'week', 1)
            ),
            nutrition AS (
                SELECT * FROM mart.fn_nutrition_trend((SELECT d FROM last_sunday), 'week', 1)
            )
            SELECT
                p.period_start,
                p.period_end,
                p.days,
                p.prev_days,
                t.sessions,
                t.prev_sessions,
                t.active_s,
                t.prev_active_s,
                t.run_m,
                t.volume_kg,
                n.days_logged,
                n.avg_kcal,
                n.prev_avg_kcal,
                n.avg_protein_g,
                round(p.avg_kg, 2),
                round(p.prev_avg_kg, 2)
            FROM per_week p
            JOIN training t ON t.period_start = p.period_start
            JOIN nutrition n ON n.period_start = p.period_start
            WHERE p.period_start = (SELECT max(period_start) FROM weeks)
        $$
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
