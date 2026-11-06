"""A Sync now request may be started without Airflow (DECISIONS D133).

In production "Sync now" asks GitHub Actions to run the pipeline workflow, which has no
Airflow run id, so ops.sync_requests.airflow_run_id becomes optional. Its progress is then
read from ops.pipeline_runs, which both schedulers write.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-06
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE ops.sync_requests ALTER COLUMN airflow_run_id DROP NOT NULL")
    op.execute(
        "COMMENT ON COLUMN ops.sync_requests.airflow_run_id IS "
        "'Airflow''s dag_run_id when Airflow ran it (local); NULL when GitHub Actions did.'"
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
