"""Server-side sessions for Google sign-in (docs/AUTH_SPEC.md section 6).

The browser's cookie holds a random 256-bit session id; this table holds only its SHA-256,
so a copy of the database cannot be turned into a working cookie.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-04
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE app.session (
            session_hash text        PRIMARY KEY CHECK (session_hash ~ '^[0-9a-f]{64}$'),
            sub          text        NOT NULL CHECK (sub <> ''),
            created_at   timestamptz NOT NULL,
            last_seen_at timestamptz NOT NULL,
            expires_at   timestamptz NOT NULL,
            CHECK (last_seen_at >= created_at),
            CHECK (expires_at > created_at)
        )
        """
    )
    # Expired rows are deleted at every sign-in by expires_at.
    op.execute("CREATE INDEX session_expires_at_idx ON app.session (expires_at)")


def downgrade() -> None:
    raise NotImplementedError("Migrations are forward-only (CLAUDE.md #6).")
