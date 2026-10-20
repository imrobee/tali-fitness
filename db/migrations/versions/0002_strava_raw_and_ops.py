"""Strava landing table and pipeline metadata tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-20
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One row per Strava activity, stored exactly as the detail endpoint returned it.
    op.execute(
        """
        CREATE TABLE raw.strava_activities (
            strava_id  bigint      PRIMARY KEY,
            payload    jsonb       NOT NULL,
            fetched_at timestamptz NOT NULL
        )
        """
    )

    # OAuth tokens live here, never in Airflow XCom (ARCHITECTURE.md section 6.1).
    op.execute(
        """
        CREATE TABLE ops.oauth_tokens (
            provider      text        PRIMARY KEY,
            access_token  text        NOT NULL,
            refresh_token text        NOT NULL,
            expires_at    timestamptz NOT NULL,
            scope         text,
            updated_at    timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    # High-water mark per source: the newest activity start time loaded so far.
    op.execute(
        """
        CREATE TABLE ops.watermarks (
            source     text        PRIMARY KEY,
            value      timestamptz NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    # One row per pipeline run. 'running' is the state while a run is in progress.
    op.execute(
        """
        CREATE TABLE ops.pipeline_runs (
            run_id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source           text        NOT NULL,
            started_at       timestamptz NOT NULL,
            finished_at      timestamptz,
            status           text        NOT NULL
                CHECK (status IN ('running', 'success', 'partial', 'failed')),
            rows_read        integer     CHECK (rows_read >= 0),
            rows_written     integer     CHECK (rows_written >= 0),
            rows_quarantined integer     CHECK (rows_quarantined >= 0),
            error_message    text,
            airflow_run_id   text,
            CHECK (finished_at IS NULL OR finished_at >= started_at)
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
