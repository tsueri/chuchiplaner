from datetime import datetime

from pydantic import BaseModel, Field


class MealSlotResponse(BaseModel):
    id: int
    week_plan_id: int
    meal_type: str
    day_of_week: int
    active: bool
    recipe_id: int | None = None
    recipe_title: str | None = None
    portions: int
    dietary_filter_tag_id: int | None = None
    cooked: bool = False
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
    dietary_filter_tag_id: int | None = None


class SlotBulkUpdate(BaseModel):
    slots: list[SlotUpdate]


class LeftoversRequest(BaseModel):
    portions_count: int = Field(ge=1)
