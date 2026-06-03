from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

CategoryType = Literal["raw", "cooked", "frozen"]


class InventoryItemCreate(BaseModel):
    ingredient_id: int
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=50)
    expiry_date: date | None = None
    category: CategoryType = "raw"


class InventoryItemUpdate(BaseModel):
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    expiry_date: date | None = None
    category: CategoryType | None = None


class InventoryItemResponse(BaseModel):
    id: int
    household_id: int
    ingredient_id: int
    ingredient_name: str = ""
    quantity: float
    unit: str
    expiry_date: date | None = None
    category: str
    source_recipe_id: int | None = None
    source_week_plan_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_serializer("expiry_date")
    def serialize_expiry_date(self, value: date | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    model_config = {"from_attributes": True}
