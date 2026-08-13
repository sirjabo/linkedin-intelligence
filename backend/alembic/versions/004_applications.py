"""004 Applications: application tracking and generated content tables.

Revision ID: 004
Revises: 003
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id", UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column(
            "job_id", UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("strategy", JSONB),
        sa.Column("notes", sa.Text),
        sa.Column("follow_up_date", sa.Date),
        sa.Column("applied_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"])
    op.create_index("ix_applications_status", "applications", ["status"])

    op.create_table(
        "cv_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id", UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("summary_adapted", sa.Text),
        sa.Column("headline_adapted", sa.String(255)),
        sa.Column("skills_ordered", JSONB),
        sa.Column("changes", JSONB),
        sa.Column("evidence_refs", JSONB),
        sa.Column("ats_keywords", JSONB),
        sa.Column("validation_result", JSONB),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "cover_letters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id", UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("evidence_refs", JSONB),
        sa.Column("validation_result", JSONB),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "application_answers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id", UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("evidence_refs", JSONB),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "application_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id", UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("occurred_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("application_events")
    op.drop_table("application_answers")
    op.drop_table("cover_letters")
    op.drop_table("cv_versions")
    op.drop_index("ix_applications_status", "applications")
    op.drop_index("ix_applications_candidate_id", "applications")
    op.drop_table("applications")
