"""Add users.hashed_password for JWT auth

Revision ID: 20250729_hashed_pw
Revises: 20250728_initial
Create Date: 2025-07-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20250729_hashed_pw"
down_revision: Union[str, None] = "20250728_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("hashed_password", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "hashed_password")
