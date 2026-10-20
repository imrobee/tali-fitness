"""Create the five warehouse schemas.

Revision ID: 0001
Revises:
Create Date: 2026-10-20
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ARCHITECTURE.md section 5:
    # raw = landing data, never edited; core = star schema; mart = business rules;
    # ops = pipeline metadata; app = user-entered data.
    op.execute("CREATE SCHEMA raw")
    op.execute("CREATE SCHEMA core")
    op.execute("CREATE SCHEMA mart")
    op.execute("CREATE SCHEMA ops")
    op.execute("CREATE SCHEMA app")


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
