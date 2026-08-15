"""Add Knowledge Base 2.0 fields to candidates.

Revision ID: 008_candidate_kb
Revises: 007_career_fit
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa

revision = "008_candidate_kb"
down_revision = "007_career_fit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("work_authorization", sa.String(100), nullable=True))
    op.add_column("candidates", sa.Column("availability", sa.String(50), nullable=True))
    op.add_column("candidates", sa.Column("career_goals", sa.Text(), nullable=True))
    op.add_column("candidates", sa.Column("salary_min_usd", sa.Integer(), nullable=True))
    op.add_column("candidates", sa.Column("languages", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "languages")
    op.drop_column("candidates", "salary_min_usd")
    op.drop_column("candidates", "career_goals")
    op.drop_column("candidates", "availability")
    op.drop_column("candidates", "work_authorization")
