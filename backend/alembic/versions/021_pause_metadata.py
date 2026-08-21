"""Add pause_metadata JSON column to application_agent_sessions.

Revision ID: 021
Revises: 020

Separates structured pause/resume metadata from the freetext error_message column.
The orchestrator previously JSON-encoded pause metadata into error_message, which
mixed two concerns. The new column holds only structured JSON; error_message remains
for human-readable error strings.
"""
import sqlalchemy as sa

from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "application_agent_sessions",
        sa.Column("pause_metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("application_agent_sessions", "pause_metadata")
