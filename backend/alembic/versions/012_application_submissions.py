"""Application submissions: track confirmed submissions with confirmation data.

Revision ID: 012_application_submissions
Revises: 011_form_intelligence
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa

revision = "012_application_submissions"
down_revision = "011_form_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_submissions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("confirmation_number", sa.String(255), nullable=True),
        sa.Column("submission_url", sa.String(2048), nullable=True),
        sa.Column("submitted_via", sa.String(100), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_application_submissions_application_id",
        "application_submissions",
        ["application_id"],
    )


def downgrade() -> None:
    op.drop_table("application_submissions")
