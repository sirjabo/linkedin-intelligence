"""001 Foundation: users, candidates, candidate_sources, candidate_profiles, evidence_records.

Also preserves legacy cv_sessions and chat_messages tables.

Revision ID: 001
Revises:
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── Candidates ─────────────────────────────────────────────────────────────
    op.create_table(
        "candidates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("name", sa.String(255)),
        sa.Column("email", sa.String(255)),
        sa.Column("location", sa.String(255)),
        sa.Column("target_roles", JSONB),
        sa.Column("preferences", JSONB),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_candidates_user_id", "candidates", ["user_id"])

    # ── Candidate Sources ──────────────────────────────────────────────────────
    op.create_table(
        "candidate_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("raw_content", sa.Text),
        sa.Column("extracted_content", JSONB),
        sa.Column("extraction_confidence", sa.Float),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_candidate_sources_candidate_id", "candidate_sources", ["candidate_id"])

    # ── Candidate Profiles ─────────────────────────────────────────────────────
    op.create_table(
        "candidate_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("summary", sa.Text),
        sa.Column("professional_identity", JSONB),
        sa.Column("career_level", sa.String(50)),
        sa.Column("industries", JSONB),
        sa.Column("competencies", JSONB),
        sa.Column("skills", JSONB),
        sa.Column("experience", JSONB),
        sa.Column("education", JSONB),
        sa.Column("projects", JSONB),
        sa.Column("certifications", JSONB),
        sa.Column("achievements", JSONB),
        sa.Column("conflicts", JSONB),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("rebuilt_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_candidate_profiles_candidate_id", "candidate_profiles", ["candidate_id"])

    # ── Evidence Records ───────────────────────────────────────────────────────
    op.create_table(
        "evidence_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim", sa.Text, nullable=False),
        sa.Column("evidence_type", sa.String(50), nullable=False),
        sa.Column("source_ref", sa.String(512)),
        sa.Column("source_text", sa.Text),
        sa.Column("strength", sa.Float),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evidence_records_candidate_id", "evidence_records", ["candidate_id"])

    # ── Legacy: cv_sessions ────────────────────────────────────────────────────
    op.create_table(
        "cv_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("original_text", sa.Text),
        sa.Column("cv_data", JSONB),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── Legacy: chat_messages ──────────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("cv_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("cv_sessions")
    op.drop_index("ix_evidence_records_candidate_id", "evidence_records")
    op.drop_table("evidence_records")
    op.drop_index("ix_candidate_profiles_candidate_id", "candidate_profiles")
    op.drop_table("candidate_profiles")
    op.drop_index("ix_candidate_sources_candidate_id", "candidate_sources")
    op.drop_table("candidate_sources")
    op.drop_index("ix_candidates_user_id", "candidates")
    op.drop_table("candidates")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
