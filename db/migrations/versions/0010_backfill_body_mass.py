"""Fill core.fact_body_mass from the body_mass samples already in raw (migration 0009 only
creates the table; the batches applied before it were never copied).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-22
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The day's last reading across every batch, the same rule as core.apply_health_batch.
    # ON CONFLICT DO NOTHING keeps a re-run harmless.
    op.execute(
        """
        INSERT INTO core.fact_body_mass
            (local_date, date_key, weight_kg, start_ts, batch_id, source)
        SELECT DISTINCT ON (s.local_date)
               s.local_date, d.date_key, s.value, s.start_ts, s.batch_id, s.source
        FROM raw.health_samples s
        JOIN core.dim_date d ON d.date = s.local_date
        WHERE s.type = 'body_mass'
        ORDER BY s.local_date, s.start_ts DESC, s.idx DESC
        ON CONFLICT (local_date) DO NOTHING
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
