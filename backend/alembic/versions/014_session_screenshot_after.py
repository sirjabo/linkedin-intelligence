"""Add screenshot_after_path to application_agent_sessions.

Revision ID: 014_session_screenshot_after
Revises: 013_application_agent_session
Create Date: 2026-08-14
"""
import sqlalchemy as sa

from alembic import op

revision = "014_session_screenshot_after"
down_revision = "013_application_agent_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "application_agent_sessions",
        sa.Column("screenshot_after_path", sa.String(1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("application_agent_sessions", "screenshot_after_path")
