"""Add skill_snapshots table for market trend history.

Revision ID: 015_skill_snapshots
Revises: 014_session_screenshot_after
Create Date: 2026-08-15
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "015_skill_snapshots"
down_revision = "014_session_screenshot_after"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("skill_slug", sa.String(128), nullable=False),
        sa.Column("skill_name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("frequency_pct", sa.Float, nullable=False),
        sa.Column("job_count", sa.Integer, nullable=False, default=0),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_skill_snapshots_role", "skill_snapshots", ["role"])
    op.create_index("ix_skill_snapshots_skill_slug", "skill_snapshots", ["skill_slug"])
    op.create_index("ix_skill_snapshots_snapshot_date", "skill_snapshots", ["snapshot_date"])
    op.create_unique_constraint(
        "uq_skill_snapshot", "skill_snapshots", ["role", "skill_slug", "snapshot_date"]
    )


def downgrade() -> None:
    op.drop_table("skill_snapshots")
