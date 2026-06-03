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
    with op.batch_alter_table("meal_slots") as batch_op:
        batch_op.add_column(
            sa.Column("cooked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
    with op.batch_alter_table("inventory_items") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source_recipe_id",
                sa.Integer(),
                sa.ForeignKey("recipes.id"),
                nullable=True,
            ),
        )
        batch_op.add_column(
            sa.Column(
                "source_week_plan_id",
                sa.Integer(),
                sa.ForeignKey("week_plans.id"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("inventory_items") as batch_op:
        batch_op.drop_column("source_week_plan_id")
        batch_op.drop_column("source_recipe_id")
    with op.batch_alter_table("meal_slots") as batch_op:
        batch_op.drop_column("cooked")
