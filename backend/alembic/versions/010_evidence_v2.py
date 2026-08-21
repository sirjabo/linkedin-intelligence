"""Evidence System 2.0: add verification_status to evidence_records.

Revision ID: 010_evidence_v2
Revises: 009_job_intelligence
Create Date: 2026-08-14
"""
import sqlalchemy as sa

from alembic import op

revision = "010_evidence_v2"
down_revision = "009_job_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evidence_records",
        sa.Column("verification_status", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evidence_records", "verification_status")
