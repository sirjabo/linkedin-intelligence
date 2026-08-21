"""Form Intelligence: application_forms and application_form_fields tables.

Revision ID: 011_form_intelligence
Revises: 010_evidence_v2
Create Date: 2026-08-14
"""
import sqlalchemy as sa

from alembic import op

revision = "011_form_intelligence"
down_revision = "010_evidence_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_forms",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("application_id", sa.Uuid(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("form_url", sa.String(2048), nullable=True),
        sa.Column("discovery_method", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("human_fields_pending", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_application_forms_application_id", "application_forms", ["application_id"])

    op.create_table(
        "application_form_fields",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("form_id", sa.Uuid(as_uuid=True), sa.ForeignKey("application_forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("field_type", sa.String(50), nullable=False, server_default="text"),
        sa.Column("semantic_type", sa.String(100), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("auto_fill_value", sa.Text(), nullable=True),
        sa.Column("human_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("human_answer", sa.Text(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_application_form_fields_form_id", "application_form_fields", ["form_id"])


def downgrade() -> None:
    op.drop_table("application_form_fields")
    op.drop_table("application_forms")
