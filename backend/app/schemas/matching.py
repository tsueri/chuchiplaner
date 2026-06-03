from typing import Literal

from pydantic import BaseModel


class MatchRequest(BaseModel):
    mode: Literal["exact", "partial", "ingredient_first"] = "partial"
    ingredient_filter: int | None = None
    dietary_filter: int | None = None
    current_plan_reservations: dict[int, dict[str, float]] | None = None


class IngredientMatchInfo(BaseModel):
    ingredient_id: int
    name: str


class ScoredRecipeResponse(BaseModel):
    recipe_id: int
    title: str
    score: float
    matched_ingredients: int
    total_ingredients: int
    missing_ingredients: list[str] = []
    urgency_boost: float = 0.0
    expiring_ingredients: list[str] = []


class MatchResponse(BaseModel):
    suggestions: list[ScoredRecipeResponse] = []
