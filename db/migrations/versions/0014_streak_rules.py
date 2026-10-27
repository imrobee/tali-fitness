"""The streak rules of Slice 7d (ARCHITECTURE.md 8): four kinds of day, breaks on a missed
day or on two over-budget or two rest days in a row, relaxed weekends and vacation periods
where only a missed day breaks. Replaces the single-freeze rule of migration 0006.

fn_day_status changes its columns, so it and the functions built on it (fn_streak,
fn_recovery_state, fn_weekly_summary) are dropped and created again. app.recovery_day
stays: a logged recovery day now marks that day as a rest day (Rob, 2026-10-27).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-27
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Relaxed weekends are a setting with history, like the targets: a change applies from
    # the day it is made, so past weekends keep the rule they had (DECISIONS D97).
    op.execute(
        """
        CREATE TABLE app.streak_settings_history (
            effective_from   date        PRIMARY KEY,
            lenient_weekends boolean     NOT NULL,
            created_at       timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    # Vacation or injury: only a missed day breaks the streak. Periods may cover past days
    # (a forgotten vacation); the API keeps them from overlapping.
    op.execute(
        """
        CREATE TABLE app.vacation (
            id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            start_date date        NOT NULL,
            end_date   date        NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (end_date >= start_date),
            CHECK (end_date - start_date < 90)
        )
        """
    )

    for function in (
        "mart.fn_weekly_summary(date)",
        "mart.fn_recovery_state(date, date)",
        "mart.fn_streak(date)",
        "mart.fn_day_status(date)",
    ):
        op.execute(f"DROP FUNCTION {function}")

    # One row per day from the first day with any data to p_today.
    #   kind: success (food logged within budget, or no budget set, and a workout),
    #         over (over budget, with or without a workout),
    #         recovery (a logged recovery day; or food within budget and no workout; or a
    #         workout and no food logged), miss (nothing logged).
    #   lenient: a vacation day, or a Saturday or Sunday while relaxed weekends are on.
    #   breaks: a miss always; otherwise, on a day that is not lenient, an over or a
    #           recovery right after a day of the same kind that was not lenient.
    #   state: counted (does not break), and for a day that breaks: pending (today, not
    #          over yet), at_risk (yesterday, can still be filled in), broken (older).
    #   island_id: broken days so far; the current streak is the counted days of the
    #              island that contains today (gaps and islands).
    op.execute(
        """
        CREATE FUNCTION mart.fn_day_status(p_today date)
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
                        AND COALESCE(
                            (SELECT s.lenient_weekends FROM app.streak_settings_history s
                             WHERE s.effective_from <= days.day
                             ORDER BY s.effective_from DESC LIMIT 1),
                            false
                        )
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

    # The current streak: counted days in the island that contains p_today. at_risk:
    # yesterday would break the streak but can still be filled in, and there is a streak
    # to protect. today_kind and yesterday_kind let the page say why.
    op.execute(
        """
        CREATE FUNCTION mart.fn_streak(p_today date)
        RETURNS TABLE (
            streak         integer,
            at_risk        boolean,
            today_state    text,
            today_kind     text,
            yesterday_kind text
        )
        LANGUAGE sql STABLE AS $$
            WITH days AS (SELECT * FROM mart.fn_day_status(p_today)),
            current_chain AS (
                SELECT d2.* FROM days d2
                WHERE d2.island_id = (SELECT d1.island_id FROM days d1 WHERE d1.day = p_today)
            ),
            counted AS (SELECT count(*)::integer AS n FROM current_chain WHERE counted)
            SELECT
                (SELECT n FROM counted),
                COALESCE(
                    (SELECT d3.state = 'at_risk' FROM days d3 WHERE d3.day = p_today - 1), false
                ) AND (SELECT n FROM counted) > 0,
                (SELECT d4.state FROM days d4 WHERE d4.day = p_today),
                (SELECT d5.kind FROM days d5 WHERE d5.day = p_today),
                (SELECT d6.kind FROM days d6 WHERE d6.day = p_today - 1)
        $$
        """
    )

    # The recovery card for p_day (UI_SPEC.md 5.4). Logging a recovery day makes the day a
    # rest day, so it helps only on a day that would break the streak, and only if the day
    # before was not a rest day already (two in a row would break it anyway).
    op.execute(
        """
        CREATE FUNCTION mart.fn_recovery_state(p_today date, p_day date) RETURNS text
        LANGUAGE sql STABLE AS $$
            WITH days AS (SELECT * FROM mart.fn_day_status(p_today)),
            this_day AS (SELECT * FROM days WHERE day = p_day),
            day_before AS (SELECT * FROM days WHERE day = p_day - 1)
            SELECT CASE
                WHEN p_day > p_today OR p_day < p_today - 1           THEN 'locked'
                WHEN COALESCE((SELECT recovery_logged FROM this_day), false) THEN 'logged'
                WHEN NOT COALESCE((SELECT breaks FROM this_day), true) THEN 'counted'
                WHEN COALESCE((SELECT lenient FROM this_day), false)    THEN 'available'
                WHEN (SELECT kind = 'recovery' AND NOT lenient FROM day_before) THEN 'blocked'
                ELSE 'available'
            END
        $$
        """
    )

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
                SELECT w.period_start, count(*) FILTER (WHERE ds.counted)::integer AS days
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
