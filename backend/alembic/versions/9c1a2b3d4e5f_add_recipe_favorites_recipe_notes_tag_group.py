"""add recipe_favorites, recipe_notes, tag group/season, FTS5

Revision ID: 9c1a2b3d4e5f
Revises: 7b0a3f2c8d1e
Create Date: 2026-06-02 23:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "9c1a2b3d4e5f"
down_revision: Union[str, Sequence[str], None] = "7b0a3f2c8d1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add group column to tags
    op.add_column(
        "tags",
        sa.Column(
            "group",
            sa.String(length=20),
            nullable=False,
            server_default="ingredient",
        ),
    )

    # Recreate tags to make household_id nullable (SQLite limitation)
    with op.batch_alter_table("tags") as batch_op:
        batch_op.alter_column("household_id", nullable=True)

    # Create recipe_favorites table
    op.create_table(
        "recipe_favorites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create recipe_notes table
    op.create_table(
        "recipe_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "visibility",
            sa.String(length=20),
            nullable=False,
            server_default="private",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create FTS5 virtual table for recipes
    op.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts USING fts5("
        "title, instructions)"
    )

    # Populate FTS with existing recipes
    op.execute(
        "INSERT INTO recipes_fts(rowid, title, instructions) "
        "SELECT id, title, instructions FROM recipes WHERE deleted_at IS NULL"
    )

    # Seed season tags
    season_tags = ["Frühling", "Sommer", "Herbst", "Winter", "Ganzjährig"]
    for name in season_tags:
        op.execute(
            f"INSERT INTO tags (name, \"group\", household_id) "
            f"VALUES ('{name}', 'season', NULL)"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recipes_fts")

    op.drop_table("recipe_notes")
    op.drop_table("recipe_favorites")

    with op.batch_alter_table("tags") as batch_op:
        batch_op.alter_column("household_id", nullable=False)
    op.drop_column("tags", "group")
    op.execute("DELETE FROM tags WHERE household_id IS NULL")
