"""Initial tables: users, job_postings, skills_catalog, skill_demand, cv_analyses

Revision ID: 20250728_initial
Revises:
Create Date: 2025-07-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20250728_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255)),
        sa.Column("target_role", sa.String(100)),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("plan_expires_at", postgresql.TIMESTAMP(timezone=True)),
        sa.Column("linkedin_url", sa.Text()),
        sa.Column("linkedin_data", postgresql.JSONB()),
        sa.Column("country", sa.String(10)),
        sa.Column("language", sa.String(10), server_default="es"),
        sa.Column("alerts_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    op.create_table(
        "skills_catalog",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("subcategory", sa.String(100)),
        sa.Column("aliases", postgresql.ARRAY(sa.Text())),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "job_postings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255)),
        sa.Column("country", sa.String(10)),
        sa.Column("remote", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("role_category", sa.String(100)),
        sa.Column("seniority", sa.String(50)),
        sa.Column("description_raw", sa.Text()),
        sa.Column("description_clean", sa.Text()),
        sa.Column("skills", postgresql.ARRAY(sa.Text())),
        sa.Column("skills_jsonb", postgresql.JSONB()),
        sa.Column("salary_min", sa.Numeric(12, 2)),
        sa.Column("salary_max", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(10)),
        sa.Column("embedding", Vector(1536)),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("posted_at", postgresql.TIMESTAMP(timezone=True)),
        sa.Column(
            "crawled_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("source", "external_id", name="uq_job_postings_source_external_id"),
    )
    op.create_index("idx_job_postings_role", "job_postings", ["role_category"])
    op.create_index("idx_job_postings_country", "job_postings", ["country"])
    op.create_index("idx_job_postings_posted_at", "job_postings", ["posted_at"])
    op.create_index("idx_job_postings_skills", "job_postings", ["skills"], postgresql_using="gin")
    op.create_index("ix_job_postings_content_hash", "job_postings", ["content_hash"])

    op.create_table(
        "skill_demand",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("skills_catalog.id")),
        sa.Column("role_category", sa.String(100), nullable=False),
        sa.Column("country", sa.String(10)),
        sa.Column("job_count", sa.Integer(), nullable=False),
        sa.Column("total_jobs", sa.Integer(), nullable=False),
        sa.Column("frequency_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("prev_week_pct", sa.Numeric(5, 2)),
        sa.Column("change_pct", sa.Numeric(5, 2)),
        sa.Column("trend", sa.String(20)),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "skill_id",
            "role_category",
            "country",
            "period_start",
            name="uq_skill_demand_skill_role_country_period",
        ),
    )
    op.create_index(
        "idx_skill_demand_role_period",
        "skill_demand",
        ["role_category", "period_start"],
    )
    op.create_index("ix_skill_demand_role_category", "skill_demand", ["role_category"])

    op.create_table(
        "cv_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("cv_text", sa.Text(), nullable=False),
        sa.Column("target_role", sa.String(100), nullable=False),
        sa.Column("target_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_postings.id")),
        sa.Column("ats_score", sa.SmallInteger()),
        sa.Column("keyword_match_pct", sa.Numeric(5, 2)),
        sa.Column("keywords_found", postgresql.JSONB()),
        sa.Column("keywords_missing", postgresql.JSONB()),
        sa.Column("section_scores", postgresql.JSONB()),
        sa.Column("suggestions", postgresql.JSONB()),
        sa.Column("cv_hash", sa.String(64)),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("ats_score BETWEEN 0 AND 100", name="ck_cv_analyses_ats_score"),
    )


def downgrade() -> None:
    op.drop_table("cv_analyses")
    op.drop_index("ix_skill_demand_role_category", table_name="skill_demand")
    op.drop_index("idx_skill_demand_role_period", table_name="skill_demand")
    op.drop_table("skill_demand")
    op.drop_index("ix_job_postings_content_hash", table_name="job_postings")
    op.drop_index("idx_job_postings_skills", table_name="job_postings")
    op.drop_index("idx_job_postings_posted_at", table_name="job_postings")
    op.drop_index("idx_job_postings_country", table_name="job_postings")
    op.drop_index("idx_job_postings_role", table_name="job_postings")
    op.drop_table("job_postings")
    op.drop_table("skills_catalog")
    op.drop_table("users")
