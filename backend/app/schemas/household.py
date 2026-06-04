from pydantic import BaseModel, Field

MEAL_TYPES = ["breakfast", "lunch", "dinner", "dessert"]


class MemberResponse(BaseModel):
    id: int
    username: str
    role: str

    model_config = {"from_attributes": True}


class HouseholdResponse(BaseModel):
    id: int
    name: str
    slug: str
    invite_code: str
    default_size: int
    default_public: bool
    members: list[MemberResponse]

    model_config = {"from_attributes": True}


class HouseholdUpdateRequest(BaseModel):
    name: str | None = None
    slug: str | None = None
    default_size: int | None = Field(default=None, ge=1)
    default_public: bool | None = None


class MealSlotTemplateResponse(BaseModel):
    id: int
    household_id: int
    day_of_week: int
    meal_type: str
    active: bool
    default_portions: int

    model_config = {"from_attributes": True}


class MealSlotTemplateUpdate(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    meal_type: str
    active: bool | None = None
    default_portions: int | None = Field(default=None, ge=1)


class MealSlotTemplateBulkUpdate(BaseModel):
    slots: list[MealSlotTemplateUpdate]
