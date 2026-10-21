"""Profile row and the recovery-card rule (ARCHITECTURE.md 5.3, UI_SPEC.md 5.4).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-21
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Exactly one row (id = 1). The timezone is shown read-only in v1; "today" comes from
    # APP_TIMEZONE on the server (same value).
    op.execute(
        """
        CREATE TABLE app.profile (
            id         integer     PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            nickname   text        CHECK (char_length(nickname) BETWEEN 1 AND 40),
            timezone   text        NOT NULL DEFAULT 'Asia/Manila',
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("INSERT INTO app.profile (id) VALUES (1)")

    # The recovery card's state for p_day, first match wins (UI_SPEC.md 5.4):
    #   locked     p_day is not today or yesterday
    #   counted    p_day already qualifies (workout + calories)
    #   logged     p_day is a valid recovery day
    #   no_freeze  the previous day was the recovery day (the freeze is in use)
    #   blocked    the previous day exists and did not qualify
    #   available  the previous day qualified, or there is no earlier data
    # POST /recovery accepts a day only when this returns 'available'.
    op.execute(
        """
        CREATE FUNCTION mart.fn_recovery_state(p_today date, p_day date) RETURNS text
        LANGUAGE sql STABLE AS $$
            WITH days AS (SELECT * FROM mart.fn_day_status(p_today))
            SELECT CASE
                WHEN p_day > p_today OR p_day < p_today - 1 THEN 'locked'
                WHEN COALESCE((SELECT qualifying FROM days WHERE day = p_day), false)
                    THEN 'counted'
                WHEN (SELECT state FROM days WHERE day = p_day) = 'recovery' THEN 'logged'
                WHEN (SELECT state FROM days WHERE day = p_day - 1) = 'recovery' THEN 'no_freeze'
                WHEN (SELECT qualifying FROM days WHERE day = p_day - 1) IS FALSE THEN 'blocked'
                ELSE 'available'
            END
        $$
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
