"""003 Match: match_analyses table.

Revision ID: 003
Revises: 002
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("overall_score", sa.Float, nullable=False),
        sa.Column("deterministic_score", sa.Float, nullable=False),
        sa.Column("llm_score", sa.Float),
        sa.Column("match_tier", sa.String(50), nullable=False),
        sa.Column("skill_overlap_score", sa.Float, nullable=False),
        sa.Column("experience_score", sa.Float, nullable=False),
        sa.Column("location_score", sa.Float, nullable=False),
        sa.Column("education_score", sa.Float, nullable=False),
        sa.Column("matched_skills", JSONB),
        sa.Column("missing_skills", JSONB),
        sa.Column("llm_reasoning", sa.Text),
        sa.Column("llm_strengths", JSONB),
        sa.Column("llm_gaps", JSONB),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_match_candidate_job"),
    )
    op.create_index("ix_match_analyses_candidate_id", "match_analyses", ["candidate_id"])
    op.create_index("ix_match_analyses_job_id", "match_analyses", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_match_analyses_job_id", "match_analyses")
    op.drop_index("ix_match_analyses_candidate_id", "match_analyses")
    op.drop_table("match_analyses")
