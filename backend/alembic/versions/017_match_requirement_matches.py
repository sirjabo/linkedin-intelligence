"""Add requirement_matches JSON column to match_analyses.

Revision ID: 017
Revises: 016
"""
import sqlalchemy as sa

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "match_analyses",
        sa.Column("requirement_matches", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("match_analyses", "requirement_matches")
