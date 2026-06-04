"""add ingredient conversion columns and seed data

Revision ID: 0c8549c26f54
Revises: h8i9j1k2l3m4
Create Date: 2026-06-04 22:51:08.821898

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0c8549c26f54"
down_revision: Union[str, Sequence[str], None] = "h8i9j1k2l3m4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ingredient(name: str, grams_per_el: float | None, grams_per_tl: float | None,
                grams_per_msp: float | None = None,
                grams_per_pris: float | None = None) -> None:
    """Update a single ingredient's conversion values."""
    sets = [f"grams_per_el = {grams_per_el}", f"grams_per_tl = {grams_per_tl}"]
    if grams_per_msp is not None:
        sets.append(f"grams_per_msp = {grams_per_msp}")
    if grams_per_pris is not None:
        sets.append(f"grams_per_pris = {grams_per_pris}")
    op.execute(
        sa.text(f"UPDATE ingredients SET {', '.join(sets)} WHERE name = '{name}'")
    )


def _seed_data() -> None:
    """Seed ~70 ingredients with conversion values from Swissmilk.de reference data."""

    # Mehl/Stärke — EL=10g, TL=3g
    for name in (
        "Backpulver", "Kakaopulver", "Maisgriess", "Maisstärke", "Mehl",
        "Milchpulver", "Natron", "Polenta", "Puderzucker", "Vollkornmehl",
    ):
        _ingredient(name, 10, 3)

    # Zucker — EL=15g, TL=5g
    for name in ("Zucker", "Vanillezucker"):
        _ingredient(name, 15, 5)

    # Salz — EL=15g, TL=5g, MSP=0.5g, Prise=1g
    _ingredient("Salz", 15, 5, grams_per_msp=0.5, grams_per_pris=1)

    # Gewürze — EL=8g, TL=4g, MSP=0.5g
    for name in (
        "Currypulver", "Gewürznelken", "Ingwer", "Kardamom", "Kreuzkümmel",
        "Kurkuma", "Muskat", "Muskatnuss", "Paprikapulver", "Pfeffer",
        "Safran", "Vanille", "Zimt",
    ):
        _ingredient(name, 8, 4, grams_per_msp=0.5)

    # Kräuter getrocknet — EL=3g, TL=1g
    for name in (
        "Basilikum", "Dill", "Estragon", "Koriander", "Kräuter",
        "Lorbeerblatt", "Minze", "Oregano", "Petersilie", "Rosmarin",
        "Salbei", "Schnittlauch", "Thymian",
    ):
        _ingredient(name, 3, 1)

    # Honig — EL=20g, TL=6g
    _ingredient("Honig", 20, 6)

    # Butter/Fett — EL=15g, TL=5g
    for name in ("Bratbutter", "Butter"):
        _ingredient(name, 15, 5)

    # Dichte Pasten — EL=20g, TL=7g
    for name in ("Erdnussbutter", "Ketchup", "Senf", "Tomatenmark", "Tomatenpüree"):
        _ingredient(name, 20, 7)

    # Trockenwaren fein — EL=12g, TL=4g
    for name in (
        "Baumnuss", "Bohnen", "Couscous", "Cranberry", "Datteln",
        "Dörrbohnen", "Erbsen", "Haferflocken", "Haselnuss", "Hirse",
        "Kokosraspeln", "Linsen", "Mandeln", "Pinienkerne", "Quinoa",
        "Reis", "Rosinen", "Sesam", "Sonnenblumenkerne",
    ):
        _ingredient(name, 12, 4)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = [c["name"] for c in inspector.get_columns("ingredients")]

    new_columns = [
        "grams_per_el", "ml_per_el", "grams_per_tl", "ml_per_tl",
        "grams_per_msp", "ml_per_msp", "grams_per_pris", "ml_per_pris",
    ]
    for col in new_columns:
        if col not in existing_columns:
            op.add_column("ingredients", sa.Column(col, sa.Float(), nullable=True))

    _seed_data()


def downgrade() -> None:
    op.drop_column("ingredients", "ml_per_pris")
    op.drop_column("ingredients", "grams_per_pris")
    op.drop_column("ingredients", "ml_per_msp")
    op.drop_column("ingredients", "grams_per_msp")
    op.drop_column("ingredients", "ml_per_tl")
    op.drop_column("ingredients", "grams_per_tl")
    op.drop_column("ingredients", "ml_per_el")
    op.drop_column("ingredients", "grams_per_el")
