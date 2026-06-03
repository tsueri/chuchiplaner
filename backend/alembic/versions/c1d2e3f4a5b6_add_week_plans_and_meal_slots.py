"""add week_plans and meal_slots

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "week_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("iso_week", sa.Integer(), nullable=False),
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", "year", "iso_week", name="uq_week_plan"),
    )

    op.create_table(
        "meal_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "week_plan_id",
            sa.Integer(),
            sa.ForeignKey("week_plans.id"),
            nullable=False,
        ),
        sa.Column("meal_type", sa.String(length=20), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "recipe_id",
            sa.Integer(),
            sa.ForeignKey("recipes.id"),
            nullable=True,
        ),
        sa.Column("portions", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "dietary_filter_tag_id",
            sa.Integer(),
            sa.ForeignKey("tags.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "week_plan_id", "day_of_week", "meal_type", name="uq_meal_slot",
        ),
    )


def downgrade() -> None:
    op.drop_table("meal_slots")
    op.drop_table("week_plans")
