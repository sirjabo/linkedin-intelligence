"""Add personalized bullet columns to cv_versions and evidence columns to application_submissions.

Sprint A: experience_personalized + projects_personalized in cv_versions
Sprint I: form_data_submitted + screenshot_confirmation_path in application_submissions

Revision ID: 016
"""
import sqlalchemy as sa

from alembic import op

revision = "016"
down_revision = "015_skill_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cv_versions", sa.Column("experience_personalized", sa.JSON(), nullable=True))
    op.add_column("cv_versions", sa.Column("projects_personalized", sa.JSON(), nullable=True))
    op.add_column("application_submissions", sa.Column("form_data_submitted", sa.JSON(), nullable=True))
    op.add_column("application_submissions", sa.Column("screenshot_confirmation_path", sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column("cv_versions", "experience_personalized")
    op.drop_column("cv_versions", "projects_personalized")
    op.drop_column("application_submissions", "form_data_submitted")
    op.drop_column("application_submissions", "screenshot_confirmation_path")
