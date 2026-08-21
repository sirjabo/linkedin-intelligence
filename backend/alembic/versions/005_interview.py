"""Phase 6 — Interview Prep table.

Revision ID: 005
Revises: 004
Create Date: 2026-08-13
"""
import sqlalchemy as sa

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_preps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("technical_questions", sa.JSON(), nullable=True),
        sa.Column("behavioral_questions", sa.JSON(), nullable=True),
        sa.Column("star_stories", sa.JSON(), nullable=True),
        sa.Column("questions_to_ask", sa.JSON(), nullable=True),
        sa.Column("company_research", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_interview_prep_application"),
    )
    op.create_index("ix_interview_preps_application_id", "interview_preps", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_interview_preps_application_id", table_name="interview_preps")
    op.drop_table("interview_preps")
