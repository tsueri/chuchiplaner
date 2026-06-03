from datetime import datetime

from pydantic import BaseModel, Field, field_serializer


class RecipeBreakdownEntry(BaseModel):
    recipe_id: int
    recipe_title: str
    quantity: float
    unit: str


class GroceryListItemResponse(BaseModel):
    id: int
    grocery_list_id: int
    ingredient_id: int | None = None
    name: str
    quantity: float
    unit: str
    checked: bool = False
    recipe_breakdown: list[RecipeBreakdownEntry] | None = None

    model_config = {"from_attributes": True}


class GroceryListResponse(BaseModel):
    id: int
    household_id: int
    week_plan_id: int | None = None
    share_token: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    items: list[GroceryListItemResponse] = []

    @field_serializer("created_at", "completed_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    model_config = {"from_attributes": True}


class GroceryListItemUpdate(BaseModel):
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    checked: bool | None = None


class GroceryListItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=50)
    ingredient_id: int | None = None


class GroceryListShareResponse(BaseModel):
    id: int
    household_name: str
    week_label: str
    items: list[GroceryListItemResponse] = []
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
