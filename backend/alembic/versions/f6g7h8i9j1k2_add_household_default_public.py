"""add household default_public

Revision ID: f6g7h8i9j1k2
Revises: e5f6g7h8i9j1
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f6g7h8i9j1k2"
down_revision: Union[str, Sequence[str], None] = "e5f6g7h8i9j1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "households",
        sa.Column("default_public", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("households", "default_public")
