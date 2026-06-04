"""seed global category, cuisine, diet tags

Revision ID: c2d3e4f5g6h7
Revises: b2c3d4e5f6a7
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c2d3e4f5g6h7"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATEGORY_TAGS = ["Vorspeise", "Hauptgericht", "Dessert", "Snack", "Beilage"]

CUISINE_TAGS = [
    "Italienisch",
    "Asiatisch",
    "Schweizerisch",
    "Mexikanisch",
    "Indisch",
    "Französisch",
]

DIET_TAGS = [
    "VegetarianDiet",
    "VeganDiet",
    "GlutenFreeDiet",
    "LowFatDiet",
    "LowLactoseDiet",
    "DiabeticDiet",
    "HalalDiet",
    "KosherDiet",
]


def upgrade() -> None:
    for name in CATEGORY_TAGS:
        op.execute(
            f"INSERT INTO tags (name, \"group\", household_id) "
            f"VALUES ('{name}', 'category', NULL)"
        )
    for name in CUISINE_TAGS:
        op.execute(
            f"INSERT INTO tags (name, \"group\", household_id) "
            f"VALUES ('{name}', 'cuisine', NULL)"
        )
    for name in DIET_TAGS:
        op.execute(
            f"INSERT INTO tags (name, \"group\", household_id) "
            f"VALUES ('{name}', 'diet', NULL)"
        )


def downgrade() -> None:
    for name in CATEGORY_TAGS:
        op.execute(f"DELETE FROM tags WHERE name = '{name}' AND \"group\" = 'category'")
    for name in CUISINE_TAGS:
        op.execute(f"DELETE FROM tags WHERE name = '{name}' AND \"group\" = 'cuisine'")
    for name in DIET_TAGS:
        op.execute(f"DELETE FROM tags WHERE name = '{name}' AND \"group\" = 'diet'")
