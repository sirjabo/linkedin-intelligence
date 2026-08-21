"""Job Intelligence 2.0: visa_sponsorship on jobs, classification on requirements.

Revision ID: 009_job_intelligence
Revises: 008_candidate_kb
Create Date: 2026-08-14
"""
import sqlalchemy as sa

from alembic import op

revision = "009_job_intelligence"
down_revision = "008_candidate_kb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("visa_sponsorship", sa.Boolean(), nullable=True))
    op.add_column("job_requirements", sa.Column("classification", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("job_requirements", "classification")
    op.drop_column("jobs", "visa_sponsorship")
