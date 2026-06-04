"""Reimport all recipes to populate ingredients."""
import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.models  # noqa: F401 — ensures all models are registered
import app.models.user  # noqa: F401 — ensure User is registered for relationships
from app.db.session import async_session
from app.models.ingredient import Ingredient, IngredientAlias
from app.models.recipe import Recipe, RecipeIngredient, RecipeTag
from app.services.ingredient_line_parser import IngredientLineParser
from app.services.normalizer import IngredientNormalizer
from app.services.scraper import RecipeScraper


async def reimport_all() -> None:
    async with async_session() as db:
        recipes = await db.execute(
            select(Recipe)
            .where(Recipe.source_url.isnot(None), Recipe.deleted_at.is_(None))
            .options(
                selectinload(Recipe.ingredients),
                selectinload(Recipe.tags).selectinload(RecipeTag.tag),
            )
        )
        recipes = recipes.unique().scalars().all()

        ingredient_rows = await db.execute(select(Ingredient))
        ingredient_map: dict[str, int] = {
            i.name: i.id for i in ingredient_rows.scalars().all()
        }

        alias_rows = await db.execute(
            select(IngredientAlias).where(IngredientAlias.household_id == 1)
        )
        household_aliases: dict[str, int] = {
            a.alias_name: a.ingredient_id for a in alias_rows.scalars().all()
        }

        normalizer = IngredientNormalizer(ingredient_map)

        total = len(recipes)
        for idx, recipe in enumerate(recipes):
            print(f"[{idx+1}/{total}] {recipe.title}")
            print(f"  URL: {recipe.source_url}")

            scraped = RecipeScraper.scrape(recipe.source_url)
            if scraped is None:
                print("  SKIP: could not scrape")
                continue

            if not scraped.ingredients:
                print("  SKIP: no ingredients found")
                continue

            for existing in list(recipe.ingredients):
                recipe.ingredients.remove(existing)
            await db.flush()

            created_count = 0
            resolved_count = 0

            for raw_line in scraped.ingredients:
                parsed = IngredientLineParser.parse(raw_line)
                if parsed.quantity is None or not parsed.name:
                    continue

                resolved_id, confidence = normalizer.resolve(
                    parsed.name, household_aliases
                )

                if resolved_id is None:
                    new_ing = Ingredient(name=parsed.name)
                    db.add(new_ing)
                    await db.flush()
                    resolved_id = new_ing.id
                    ingredient_map[parsed.name] = resolved_id
                    household_aliases[parsed.name] = resolved_id
                    alias = IngredientAlias(
                        household_id=recipe.household_id,
                        alias_name=parsed.name,
                        ingredient_id=resolved_id,
                    )
                    db.add(alias)
                    created_count += 1

                unit = parsed.unit or "Stück"
                qty = parsed.quantity

                recipe.ingredients.append(
                    RecipeIngredient(
                        recipe_id=recipe.id,
                        ingredient_id=resolved_id,
                        quantity=qty,
                        unit=unit,
                        order_index=len(recipe.ingredients),
                    )
                )
                resolved_count += 1

            await db.flush()
            print(f"  OK: {resolved_count} ingredients ({created_count} created)")

        await db.commit()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(reimport_all())
