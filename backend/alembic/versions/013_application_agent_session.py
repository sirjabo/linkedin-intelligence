"""ApplicationAgentSession: tracks browser-based form-filling lifecycle.

Revision ID: 013_application_agent_session
Revises: 012_application_submissions
Create Date: 2026-08-14
"""
import sqlalchemy as sa

from alembic import op

revision = "013_application_agent_session"
down_revision = "012_application_submissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_agent_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # State machine
        sa.Column("status", sa.String(50), nullable=False, server_default="initializing"),
        # ATS metadata
        sa.Column("ats_name", sa.String(100), nullable=True),
        sa.Column("form_url", sa.String(2048), nullable=True),
        # Field counters
        sa.Column("fields_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fields_auto_filled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fields_human_pending", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fields_confirmed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fields_skipped", sa.Integer(), nullable=False, server_default="0"),
        # Confidence metrics
        sa.Column("avg_confidence", sa.Float(), nullable=True),
        sa.Column("min_confidence", sa.Float(), nullable=True),
        # Submission outcome
        sa.Column("confirmation_id", sa.String(255), nullable=True),
        sa.Column("final_url", sa.String(2048), nullable=True),
        # Human review
        sa.Column("human_review_requested", sa.String(1), nullable=False, server_default="0"),
        sa.Column("human_confirmed", sa.String(1), nullable=False, server_default="0"),
        # Screenshot artifacts
        sa.Column("screenshot_before_path", sa.String(1024), nullable=True),
        sa.Column("screenshot_filled_path", sa.String(1024), nullable=True),
        sa.Column("screenshot_confirm_path", sa.String(1024), nullable=True),
        # Error tracking
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        # Timestamps
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("discovered_at", sa.DateTime(), nullable=True),
        sa.Column("filled_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_application_agent_sessions_application_id",
        "application_agent_sessions",
        ["application_id"],
    )
    op.create_index(
        "ix_application_agent_sessions_status",
        "application_agent_sessions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_table("application_agent_sessions")
