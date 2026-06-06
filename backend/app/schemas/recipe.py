from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_serializer


class RecipeImportRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class RecipeIngredientResponse(BaseModel):
    id: int
    ingredient_id: int
    quantity: float
    unit: str
    order_index: int
    ingredient_name: str

    model_config = {"from_attributes": True}


class RecipeStepResponse(BaseModel):
    id: int
    position: int
    text: str
    name: str | None = None

    model_config = {"from_attributes": True}


class RecipeResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    image_url: str | None = None
    source_url: str | None = None
    source_domain: str | None = None
    servings: int
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    total_time_minutes: int | None = None
    perform_time_minutes: int | None = None
    nutrition: dict[str, Any] | None = None
    aggregate_rating: dict[str, Any] | None = None
    keywords: str | None = None
    author: str | None = None
    date_published: date | None = None
    household_id: int
    ingredients: list[RecipeIngredientResponse] = []
    steps: list[RecipeStepResponse] = []
    created_at: datetime | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    @field_serializer("date_published")
    def serialize_date_published(self, value: date | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    model_config = {"from_attributes": True}


class ScrapedIngredientItem(BaseModel):
    raw: str
    name: str
    quantity: float | None = None
    unit: str | None = None
    ingredient_id: int | None = None
    confidence: float = 0.0
    tier1_cleaned_name: str | None = None
    tier2_cleaned_name: str | None = None
    corrected_quantity: float | None = None
    corrected_unit: str | None = None
    suggested_ingredient_name: str | None = None
    is_equipment: bool = False


class ScrapedStepItem(BaseModel):
    position: int = 0
    text: str
    name: str | None = None


class ScrapedRecipeResponse(BaseModel):
    title: str
    ingredients: list[ScrapedIngredientItem]
    image_url: str | None = None
    servings: int
    source_url: str
    source_domain: str
    existing_recipe_id: int | None = None
    is_partial: bool = False
    steps: list[ScrapedStepItem] = []
    description: str | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    total_time_minutes: int | None = None
    perform_time_minutes: int | None = None
    author: str | None = None
    date_published: date | None = None
    keywords: str | None = None
    ratings: float | None = None
    nutrients: dict[str, Any] | None = None
    suitable_for_diet_tag_ids: list[int] = []

    @field_serializer("date_published")
    def serialize_date_published(self, value: date | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()


class LearnedAliasItem(BaseModel):
    alias_name: str = Field(min_length=1, max_length=255)
    ingredient_id: int


class RecipeStepItem(BaseModel):
    position: int = 0
    text: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=255)


class RecipeSaveRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2048)
    image_url: str | None = Field(default=None, max_length=2048)
    source_url: str | None = Field(default=None, max_length=2048)
    source_domain: str | None = Field(default=None, max_length=255)
    servings: int = Field(default=4, ge=1)
    prep_time_minutes: int | None = Field(default=None, ge=0)
    cook_time_minutes: int | None = Field(default=None, ge=0)
    total_time_minutes: int | None = Field(default=None, ge=0)
    perform_time_minutes: int | None = Field(default=None, ge=0)
    nutrition: dict[str, Any] | None = None
    aggregate_rating: dict[str, Any] | None = None
    keywords: str | None = None
    author: str | None = Field(default=None, max_length=255)
    date_published: date | None = None
    ingredients: list["RecipeIngredientItem"] = Field(default_factory=list)
    steps: list["RecipeStepItem"] = Field(default_factory=list)
    learned_aliases: list["LearnedAliasItem"] = Field(default_factory=list)
    tag_ids: list[int] | None = None
    reimport: bool = False


class RecipeIngredientItem(BaseModel):
    ingredient_id: int
    quantity: float
    unit: str = Field(min_length=1, max_length=50)
    order_index: int = 0
    suggested_ingredient_name: str | None = None
    original_name: str | None = None


class TagResponse(BaseModel):
    id: int
    name: str
    group: str
    household_id: int | None = None

    model_config = {"from_attributes": True}


class TagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    group: str = Field(
        default="ingredient",
        pattern=r"^(season|ingredient|category|cuisine|diet)$",
    )


class RecipeFavoriteResponse(BaseModel):
    id: int
    user_id: int
    recipe_id: int
    created_at: datetime | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    model_config = {"from_attributes": True}


class RecipeNoteResponse(BaseModel):
    id: int
    recipe_id: int
    user_id: int
    text: str
    visibility: str
    username: str | None = None
    recipe_title: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    @field_serializer("updated_at")
    def serialize_updated_at(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    model_config = {"from_attributes": True}


class RecipeNoteCreateRequest(BaseModel):
    text: str = Field(min_length=1)
    visibility: str = Field(default="private", pattern=r"^(private|household)$")


class RecipeNoteUpdateRequest(BaseModel):
    text: str = Field(min_length=1)
    visibility: str | None = Field(default=None, pattern=r"^(private|household)$")


class RecipeDetailResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    image_url: str | None = None
    source_url: str | None = None
    source_domain: str | None = None
    servings: int
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    total_time_minutes: int | None = None
    perform_time_minutes: int | None = None
    nutrition: dict[str, Any] | None = None
    aggregate_rating: dict[str, Any] | None = None
    keywords: str | None = None
    author: str | None = None
    date_published: date | None = None
    household_id: int
    ingredients: list[RecipeIngredientResponse] = []
    steps: list[RecipeStepResponse] = []
    tags: list[TagResponse] = []
    is_favorited: bool = False
    created_at: datetime | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    @field_serializer("date_published")
    def serialize_date_published(self, value: date | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    model_config = {"from_attributes": True}


class RecipeListResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    image_url: str | None = None
    source_url: str | None = None
    source_domain: str | None = None
    servings: int
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    total_time_minutes: int | None = None
    perform_time_minutes: int | None = None
    nutrition: dict[str, Any] | None = None
    aggregate_rating: dict[str, Any] | None = None
    keywords: str | None = None
    author: str | None = None
    date_published: date | None = None
    household_id: int
    tags: list[TagResponse] = []
    is_favorited: bool = False
    ingredients: list[RecipeIngredientResponse] = []
    steps: list[RecipeStepResponse] = []
    created_at: datetime | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    @field_serializer("date_published")
    def serialize_date_published(self, value: date | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    model_config = {"from_attributes": True}


class RecipeUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2048)
    image_url: str | None = Field(default=None, max_length=2048)
    source_url: str | None = Field(default=None, max_length=2048)
    source_domain: str | None = Field(default=None, max_length=255)
    servings: int | None = Field(default=None, ge=1)
    prep_time_minutes: int | None = Field(default=None, ge=0)
    cook_time_minutes: int | None = Field(default=None, ge=0)
    total_time_minutes: int | None = Field(default=None, ge=0)
    perform_time_minutes: int | None = Field(default=None, ge=0)
    nutrition: dict[str, Any] | None = None
    aggregate_rating: dict[str, Any] | None = None
    keywords: str | None = None
    author: str | None = Field(default=None, max_length=255)
    date_published: date | None = None
    tag_ids: list[int] | None = None
    ingredients: list["RecipeIngredientItem"] | None = None
    steps: list["RecipeStepItem"] | None = None


class CookRequest(BaseModel):
    portions: int = Field(ge=1)
    slot_id: int | None = None
    year: int | None = None
    iso_week: int | None = None


class LeftoversRequest(BaseModel):
    portions_count: int = Field(ge=1)
    slot_id: int | None = None
    year: int | None = None
    iso_week: int | None = None
