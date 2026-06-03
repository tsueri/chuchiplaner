"""add grocery lists and grocery list items

Revision ID: e5f6g7h8i9j1
Revises: d2e3f4g5h6i7
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6g7h8i9j1"
down_revision: Union[str, Sequence[str], None] = "d2e3f4g5h6i7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "grocery_lists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column(
            "week_plan_id",
            sa.Integer(),
            sa.ForeignKey("week_plans.id"),
            nullable=True,
        ),
        sa.Column("share_token", sa.String(64), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "grocery_list_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "grocery_list_id",
            sa.Integer(),
            sa.ForeignKey("grocery_lists.id"),
            nullable=False,
        ),
        sa.Column(
            "ingredient_id",
            sa.Integer(),
            sa.ForeignKey("ingredients.id"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("checked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("recipe_breakdown", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("grocery_list_items")
    op.drop_table("grocery_lists")
