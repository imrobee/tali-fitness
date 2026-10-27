"""The weight unit preference (kg or lb) and a goal precise enough for pounds.

Weights stay stored in kg; the preference only changes how they are shown and entered.
A goal typed as 160 lb is 72.5747792 kg: with 3 decimals it reads back as 160.0 lb,
where numeric(5,1) would read back as 160.1.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-22
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE app.profile
            ADD COLUMN weight_unit text NOT NULL DEFAULT 'kg'
                CHECK (weight_unit IN ('kg', 'lb'))
        """
    )
    op.execute("ALTER TABLE app.weight_goal_history ALTER COLUMN goal_kg TYPE numeric(7,3)")


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
