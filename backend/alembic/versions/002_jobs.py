"""002 Jobs: jobs and job_requirements tables.

Revision ID: 002
Revises: 001
Create Date: 2026-08-13
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("company", sa.String(255)),
        sa.Column("job_url", sa.String(2048)),
        sa.Column("location", sa.String(255)),
        sa.Column("remote_type", sa.String(50)),
        sa.Column("seniority", sa.String(50)),
        sa.Column("employment_type", sa.String(50)),
        sa.Column("salary_min", sa.Integer),
        sa.Column("salary_max", sa.Integer),
        sa.Column("salary_currency", sa.String(10)),
        sa.Column("tech_stack", JSONB),
        sa.Column("key_responsibilities", JSONB),
        sa.Column("company_description", sa.Text),
        sa.Column("parsing_confidence", sa.Float),
        sa.Column("raw_jd", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="analyzed"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_candidate_id", "jobs", ["candidate_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "job_requirements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("requirement_type", sa.String(50), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("seniority_signal", sa.String(100)),
    )
    op.create_index("ix_job_requirements_job_id", "job_requirements", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_job_requirements_job_id", "job_requirements")
    op.drop_table("job_requirements")
    op.drop_index("ix_jobs_status", "jobs")
    op.drop_index("ix_jobs_candidate_id", "jobs")
    op.drop_table("jobs")
