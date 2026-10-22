"""Sync now (PROJECT_PLAN Slice 7c): one row per "Sync now" request, for the 2-minute
cooldown and for the page to follow the Airflow run it started.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-22
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE ops.sync_requests (
            id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source         text        NOT NULL CHECK (source IN ('strava')),
            requested_at   timestamptz NOT NULL,
            airflow_run_id text        NOT NULL
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
