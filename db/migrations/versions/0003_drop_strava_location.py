"""Remove location data from Strava activities already landed.

From now on sync.py drops these fields before landing (DECISIONS D24); this removes
them from rows loaded before that change. The fields are never used downstream.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-20
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # jsonb "-" removes a top-level key; removing a key that is absent is a no-op.
    op.execute(
        """
        UPDATE raw.strava_activities
        SET payload = payload - 'map' - 'start_latlng' - 'end_latlng' - 'segment_efforts'
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
