from datetime import datetime

from pydantic import BaseModel, Field


class PlannedRecipeResponse(BaseModel):
    id: int
    recipe_id: int
    recipe_title: str | None = None
    portions: int
    cooked: bool = False

    model_config = {"from_attributes": True}


class PlannedRecipeInput(BaseModel):
    recipe_id: int
    portions: int = Field(default=1, ge=1)


class MealSlotResponse(BaseModel):
    id: int
    week_plan_id: int
    meal_type: str
    day_of_week: int
    active: bool
    planned_recipes: list[PlannedRecipeResponse] = []
    portions: int
    dietary_filter_tag_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class WeekPlanResponse(BaseModel):
    id: int
    household_id: int
    year: int
    iso_week: int
    is_public: bool
    created_at: datetime | None = None
    slots: list[MealSlotResponse] = []

    model_config = {"from_attributes": True}


class WeekPlanListItem(BaseModel):
    id: int
    household_id: int
    year: int
    iso_week: int
    is_public: bool
    created_at: datetime | None = None
    planned_count: int = 0
    total_slots: int = 0

    model_config = {"from_attributes": True}


class WeekPlanCreateRequest(BaseModel):
    year: int
    iso_week: int
    copy_from_previous: bool = False


class SlotUpdate(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    meal_type: str
    recipe_id: int | None = None
    portions: int | None = Field(default=None, ge=1)
    planned_recipes: list[PlannedRecipeInput] = []
    dietary_filter_tag_id: int | None = None


class SlotBulkUpdate(BaseModel):
    slots: list[SlotUpdate]


class LeftoversRequest(BaseModel):
    portions_count: int = Field(ge=1)


class VisibilityUpdateRequest(BaseModel):
    is_public: bool
