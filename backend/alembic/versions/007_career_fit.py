"""Add career_fit_score, application_decision, hard_blockers to match_analyses.

Revision ID: 007_career_fit
Revises: 006_match_outcome
Create Date: 2026-08-14
"""
import sqlalchemy as sa

from alembic import op

revision = "007_career_fit"
down_revision = "006_match_outcome"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("match_analyses", sa.Column("career_fit_score", sa.Float(), nullable=True))
    op.add_column("match_analyses", sa.Column("application_decision", sa.String(50), nullable=True))
    op.add_column("match_analyses", sa.Column("hard_blockers", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("match_analyses", "hard_blockers")
    op.drop_column("match_analyses", "application_decision")
    op.drop_column("match_analyses", "career_fit_score")
