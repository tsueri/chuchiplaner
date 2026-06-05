"""add planned_recipes junction table

Revision ID: i9j1k2l3m4n5
Revises: 0c8549c26f54
Create Date: 2026-06-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "i9j1k2l3m4n5"
down_revision: Union[str, Sequence[str], None] = "0c8549c26f54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "planned_recipes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meal_slot_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column(
            "portions", sa.Integer(), nullable=False, server_default=sa.text("1"),
        ),
        sa.Column("cooked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "order_index", sa.Integer(), nullable=False, server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["meal_slot_id"], ["meal_slots.id"],
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"], ["recipes.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "meal_slot_id", "recipe_id", name="uq_planned_recipe"
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO planned_recipes "
            "(meal_slot_id, recipe_id, portions, cooked, order_index, "
            "created_at, updated_at) "
            "SELECT id, recipe_id, portions, cooked, 0, "
            "COALESCE(created_at, CURRENT_TIMESTAMP), "
            "COALESCE(updated_at, CURRENT_TIMESTAMP) "
            "FROM meal_slots WHERE recipe_id IS NOT NULL"
        )
    )
    with op.batch_alter_table("meal_slots") as batch_op:
        batch_op.drop_column("cooked")
        batch_op.drop_column("recipe_id")


def downgrade() -> None:
    with op.batch_alter_table("meal_slots") as batch_op:
        batch_op.add_column(
            sa.Column("recipe_id", sa.Integer(), nullable=True),
        )
        batch_op.add_column(
            sa.Column(
                "cooked",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
    op.execute(
        sa.text(
            "UPDATE meal_slots SET "
            "recipe_id = (SELECT pr.recipe_id FROM planned_recipes pr "
            "WHERE pr.meal_slot_id = meal_slots.id AND pr.order_index = 0 LIMIT 1), "
            "cooked = COALESCE((SELECT pr.cooked FROM planned_recipes pr "
            "WHERE pr.meal_slot_id = meal_slots.id AND pr.order_index = 0 LIMIT 1), 0)"
        )
    )
    op.drop_table("planned_recipes")
