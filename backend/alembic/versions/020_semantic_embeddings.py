"""Add semantic scoring columns and pgvector embedding columns.

Revision ID: 020
Revises: 019

Adds:
- match_analyses.semantic_score (Float)
- match_analyses.top_evidence (JSON)
- pgvector extension (if not already installed)
- jobs.embedding vector(1536)
- candidate_profiles.embedding vector(1536)
- evidence_records.embedding vector(1536)
- HNSW indexes on embedding columns for cosine similarity search
"""
import sqlalchemy as sa
from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Scalar columns on match_analyses (no extension needed)
    op.add_column("match_analyses", sa.Column("semantic_score", sa.Float(), nullable=True))
    op.add_column("match_analyses", sa.Column("top_evidence", sa.JSON(), nullable=True))

    # pgvector extension — CREATE EXTENSION IF NOT EXISTS is idempotent
    # Skip gracefully if the extension is not available in this deployment
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

        op.execute(
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS embedding vector(1536)"
        )
        op.execute(
            "ALTER TABLE candidate_profiles ADD COLUMN IF NOT EXISTS embedding vector(1536)"
        )
        op.execute(
            "ALTER TABLE evidence_records ADD COLUMN IF NOT EXISTS embedding vector(1536)"
        )

        # HNSW index for approximate nearest-neighbour cosine search (pgvector 0.5+)
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_embedding "
            "ON jobs USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_evidence_embedding "
            "ON evidence_records USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_profile_embedding "
            "ON candidate_profiles USING hnsw (embedding vector_cosine_ops)"
        )
    except Exception:
        # pgvector not installed — vector columns skipped; semantic scoring
        # still works in-memory without them
        pass


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_embedding")
    op.execute("DROP INDEX IF EXISTS idx_evidence_embedding")
    op.execute("DROP INDEX IF EXISTS idx_profile_embedding")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE candidate_profiles DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE evidence_records DROP COLUMN IF EXISTS embedding")
    op.drop_column("match_analyses", "top_evidence")
    op.drop_column("match_analyses", "semantic_score")
