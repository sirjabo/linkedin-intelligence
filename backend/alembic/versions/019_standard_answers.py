"""Create standard_answers table.

Revision ID: 019
Revises: 018
"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "standard_answers",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("question_type", sa.String(80), nullable=False),
        sa.Column("label", sa.String(255), nullable=False, default=""),
        sa.Column("answer_text", sa.Text, nullable=False),
        sa.Column("applies_to_seniority", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("standard_answers")
