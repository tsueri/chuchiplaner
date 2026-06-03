"""recipe model v2: drop instructions, add recipe_steps + 9 nullable columns,
expand tags.group, rebuild recipes_fts

Revision ID: b2c3d4e5f6a7
Revises: a7b8c9d0e1f2
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recipe_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recipe_id", "position", name="uq_recipe_steps_recipe_position"
        ),
    )

    op.execute(
        "INSERT INTO recipe_steps (recipe_id, position, text, name) "
        "SELECT id, 0, instructions, NULL FROM recipes"
    )

    with op.batch_alter_table("recipes") as batch_op:
        batch_op.drop_column("instructions")
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("prep_time_minutes", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("cook_time_minutes", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("total_time_minutes", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("perform_time_minutes", sa.Integer(), nullable=True)
        )
        batch_op.add_column(sa.Column("nutrition", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("aggregate_rating", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("keywords", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("author", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("date_published", sa.Date(), nullable=True))

    with op.batch_alter_table("tags") as batch_op:
        batch_op.alter_column(
            "group",
            existing_type=sa.String(length=20),
            type_=sa.String(length=20),
            existing_nullable=False,
            server_default="ingredient",
        )

    op.execute("DROP TABLE IF EXISTS recipes_fts")
    op.execute(
        "CREATE VIRTUAL TABLE recipes_fts USING fts5("
        "title, description, steps, ingredients, keywords, author, tags)"
    )

    op.execute(
        "INSERT INTO recipes_fts(rowid, title, description, steps, "
        "ingredients, keywords, author, tags) "
        "SELECT r.id, r.title, COALESCE(r.description, ''), "
        "COALESCE((SELECT GROUP_CONCAT(text, ' ') FROM recipe_steps "
        "WHERE recipe_id = r.id), ''), "
        "COALESCE((SELECT GROUP_CONCAT(i.name, ' ') "
        "FROM recipe_ingredients ri JOIN ingredients i "
        "ON ri.ingredient_id = i.id WHERE ri.recipe_id = r.id), ''), "
        "COALESCE(r.keywords, ''), COALESCE(r.author, ''), "
        "COALESCE((SELECT GROUP_CONCAT(t.name, ' ') "
        "FROM recipe_tags rt JOIN tags t ON rt.tag_id = t.id "
        "WHERE rt.recipe_id = r.id), '') "
        "FROM recipes r"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recipes_fts")
    op.execute(
        "CREATE VIRTUAL TABLE recipes_fts USING fts5("
        "title, instructions)"
    )

    with op.batch_alter_table("recipes") as batch_op:
        batch_op.add_column(sa.Column("instructions", sa.Text(), nullable=True))
        batch_op.drop_column("date_published")
        batch_op.drop_column("author")
        batch_op.drop_column("keywords")
        batch_op.drop_column("aggregate_rating")
        batch_op.drop_column("nutrition")
        batch_op.drop_column("perform_time_minutes")
        batch_op.drop_column("total_time_minutes")
        batch_op.drop_column("cook_time_minutes")
        batch_op.drop_column("prep_time_minutes")
        batch_op.drop_column("description")

    op.execute(
        "UPDATE recipes SET instructions = ("
        "SELECT text FROM recipe_steps WHERE recipe_id = recipes.id "
        "ORDER BY position LIMIT 1"
        ") WHERE EXISTS ("
        "SELECT 1 FROM recipe_steps WHERE recipe_id = recipes.id"
        ")"
    )
    op.execute(
        "UPDATE recipes SET instructions = '' "
        "WHERE instructions IS NULL"
    )

    with op.batch_alter_table("recipes") as batch_op:
        batch_op.alter_column("instructions", nullable=False)

    op.execute(
        "INSERT INTO recipes_fts(rowid, title, instructions) "
        "SELECT id, title, instructions FROM recipes"
    )

    op.drop_table("recipe_steps")
