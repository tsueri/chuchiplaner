from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class IngredientAvailability:
    ingredient_id: int
    name: str = ""
    grams: float = 0.0
    milliliters: float = 0.0
    pieces: float = 0.0
    has_expiring: bool = False


@dataclass
class RecipeIngredientNeed:
    ingredient_id: int
    name: str = ""
    grams: float = 0.0
    milliliters: float = 0.0
    pieces: float = 0.0


@dataclass
class RecipeInfo:
    id: int
    title: str = ""
    ingredients: list[RecipeIngredientNeed] = field(default_factory=list)
    tag_names: list[str] = field(default_factory=list)


@dataclass
class ScoredRecipe:
    recipe_id: int
    title: str = ""
    score: float = 0.0
    matched_ingredients: int = 0
    total_ingredients: int = 0
    missing_ingredients: list[str] = field(default_factory=list)
    urgency_boost: float = 0.0
    expiring_ingredients: list[str] = field(default_factory=list)


class MatchingEngine:
    URGENCY_BOOST = 0.1

    @staticmethod
    def suggest(
        inventory: dict[int, IngredientAvailability],
        recipes: list[RecipeInfo],
        mode: Literal["exact", "partial", "ingredient_first"],
        ingredient_filter: int | None = None,
        dietary_filter: str | None = None,
        current_plan_reservations: dict[int, tuple[float, float, float]] | None = None,
    ) -> list[ScoredRecipe]:
        if not recipes or (mode != "partial" and not inventory):
            return []

        if mode == "ingredient_first" and ingredient_filter is not None:
            recipes = [
                r for r in recipes
                if any(i.ingredient_id == ingredient_filter for i in r.ingredients)
            ]

        if dietary_filter is not None:
            df_lower = dietary_filter.lower()
            recipes = [
                r for r in recipes
                if any(t.lower() == df_lower for t in r.tag_names)
            ]

        effective_inventory = dict(inventory)
        if current_plan_reservations:
            effective_inventory = {}
            for ing_id, avail in inventory.items():
                res = current_plan_reservations.get(ing_id, (0, 0, 0))
                effective_inventory[ing_id] = IngredientAvailability(
                    ingredient_id=avail.ingredient_id,
                    name=avail.name,
                    grams=max(0, avail.grams - res[0]),
                    milliliters=max(0, avail.milliliters - res[1]),
                    pieces=max(0, avail.pieces - res[2]),
                    has_expiring=avail.has_expiring,
                )

        scored: list[ScoredRecipe] = []
        for recipe in recipes:
            result = MatchingEngine._score_recipe(recipe, effective_inventory)
            if mode == "exact" and result.score < 1.0:
                continue
            scored.append(result)

        scored.sort(key=lambda s: s.score, reverse=True)
        return scored

    @staticmethod
    def _score_recipe(
        recipe: RecipeInfo,
        inventory: dict[int, IngredientAvailability],
    ) -> ScoredRecipe:
        total = len(recipe.ingredients)
        if total == 0:
            return ScoredRecipe(
                recipe_id=recipe.id, title=recipe.title,
                score=0.0, total_ingredients=0,
            )

        matched = 0
        missing: list[str] = []
        expiring: list[str] = []
        has_any_expiring = False

        for need in recipe.ingredients:
            avail = inventory.get(need.ingredient_id)
            is_satisfied = MatchingEngine._check_availability(need, avail)

            if is_satisfied:
                matched += 1
                if avail and avail.has_expiring:
                    has_any_expiring = True
                    expiring.append(avail.name)
            else:
                missing.append(need.name)

        base_score = matched / total
        urgency_boost = MatchingEngine.URGENCY_BOOST if has_any_expiring else 0.0
        score = base_score + urgency_boost

        return ScoredRecipe(
            recipe_id=recipe.id,
            title=recipe.title,
            score=score,
            matched_ingredients=matched,
            total_ingredients=total,
            missing_ingredients=missing,
            urgency_boost=urgency_boost,
            expiring_ingredients=expiring,
        )

    @staticmethod
    def _check_availability(
        need: RecipeIngredientNeed,
        avail: IngredientAvailability | None,
    ) -> bool:
        if avail is None:
            return False
        if need.grams > 0 and avail.grams < need.grams:
            return False
        if need.milliliters > 0 and avail.milliliters < need.milliliters:
            return False
        if need.pieces > 0 and avail.pieces < need.pieces:
            return False
        return True
