"""Add jd_hash column + unique constraint to jobs for deduplication.

Revision ID: 018
Revises: 017
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("jd_hash", sa.String(64), nullable=True),
    )
    op.create_index("ix_jobs_jd_hash", "jobs", ["jd_hash"])
    op.create_unique_constraint("uq_job_candidate_jd_hash", "jobs", ["candidate_id", "jd_hash"])


def downgrade() -> None:
    op.drop_constraint("uq_job_candidate_jd_hash", "jobs", type_="unique")
    op.drop_index("ix_jobs_jd_hash", "jobs")
    op.drop_column("jobs", "jd_hash")
