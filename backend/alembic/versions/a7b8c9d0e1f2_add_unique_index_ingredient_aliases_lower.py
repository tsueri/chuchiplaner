"""add unique index on ingredient_aliases(household_id, lower(alias_name))

Revision ID: a7b8c9d0e1f2
Revises: f6g7h8i9j1k2
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6g7h8i9j1k2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_ingredient_aliases_household_lower_alias",
        "ingredient_aliases",
        ["household_id", sa.text("LOWER(alias_name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_ingredient_aliases_household_lower_alias",
        table_name="ingredient_aliases",
    )
