"""add generated_at to grocery_lists

Revision ID: g7h8i9j1k2l3
Revises: c2d3e4f5g6h7
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "g7h8i9j1k2l3"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5g6h7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "grocery_lists",
        sa.Column("generated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("grocery_lists", "generated_at")
