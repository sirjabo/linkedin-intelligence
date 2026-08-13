"""Add outcome column to match_analyses for learning loop.

Revision ID: 006_match_outcome
Revises: 005_interview
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "006_match_outcome"
down_revision = "005_interview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "match_analyses",
        sa.Column("outcome", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("match_analyses", "outcome")
