"""add meal_slots cooked and inventory source

Revision ID: d2e3f4g5h6i7
Revises: c1d2e3f4a5b6
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d2e3f4g5h6i7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meal_slots",
        sa.Column("cooked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "inventory_items",
        sa.Column(
            "source_recipe_id",
            sa.Integer(),
            sa.ForeignKey("recipes.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "inventory_items",
        sa.Column(
            "source_week_plan_id",
            sa.Integer(),
            sa.ForeignKey("week_plans.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("inventory_items", "source_week_plan_id")
    op.drop_column("inventory_items", "source_recipe_id")
    op.drop_column("meal_slots", "cooked")
