from pydantic import BaseModel


class PublicRecipeResponse(BaseModel):
    id: int
    title: str
    image_url: str | None = None
    source_url: str | None = None
    source_domain: str | None = None
    servings: int

    model_config = {"from_attributes": True}


class PublicPlannedRecipeResponse(BaseModel):
    recipe: PublicRecipeResponse | None = None
    portions: int
    cooked: bool = False


class PublicMealSlotResponse(BaseModel):
    id: int
    meal_type: str
    day_of_week: int
    active: bool
    recipe: PublicRecipeResponse | None = None
    portions: int
    cooked: bool
    planned_recipes: list[PublicPlannedRecipeResponse] = []

    model_config = {"from_attributes": True}


class PublicWeekPlanResponse(BaseModel):
    household_name: str
    household_slug: str
    year: int
    iso_week: int
    slots: list[PublicMealSlotResponse]
