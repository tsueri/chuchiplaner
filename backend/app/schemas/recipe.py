from datetime import datetime

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


class RecipeResponse(BaseModel):
    id: int
    title: str
    instructions: str
    image_url: str | None = None
    source_url: str | None = None
    source_domain: str | None = None
    servings: int
    household_id: int
    ingredients: list[RecipeIngredientResponse] = []
    created_at: datetime | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
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


class ScrapedRecipeResponse(BaseModel):
    title: str
    ingredients: list[ScrapedIngredientItem]
    instructions: str
    image_url: str | None = None
    servings: int
    source_url: str
    source_domain: str
    existing_recipe_id: int | None = None
    is_partial: bool = False


class LearnedAliasItem(BaseModel):
    alias_name: str = Field(min_length=1, max_length=255)
    ingredient_id: int


class RecipeSaveRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    instructions: str = Field(min_length=1)
    image_url: str | None = Field(default=None, max_length=2048)
    source_url: str | None = Field(default=None, max_length=2048)
    source_domain: str | None = Field(default=None, max_length=255)
    servings: int = Field(default=4, ge=1)
    ingredients: list["RecipeIngredientItem"] = Field(default_factory=list)
    learned_aliases: list["LearnedAliasItem"] = Field(default_factory=list)


class RecipeIngredientItem(BaseModel):
    ingredient_id: int
    quantity: float
    unit: str = Field(min_length=1, max_length=50)
    order_index: int = 0


class TagResponse(BaseModel):
    id: int
    name: str
    group: str
    household_id: int | None = None

    model_config = {"from_attributes": True}


class TagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


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
    instructions: str
    image_url: str | None = None
    source_url: str | None = None
    source_domain: str | None = None
    servings: int
    household_id: int
    ingredients: list[RecipeIngredientResponse] = []
    tags: list[TagResponse] = []
    is_favorited: bool = False
    created_at: datetime | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    model_config = {"from_attributes": True}


class RecipeListResponse(BaseModel):
    id: int
    title: str
    instructions: str
    image_url: str | None = None
    source_url: str | None = None
    source_domain: str | None = None
    servings: int
    household_id: int
    tags: list[TagResponse] = []
    is_favorited: bool = False
    ingredients: list[RecipeIngredientResponse] = []
    created_at: datetime | None = None

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    model_config = {"from_attributes": True}


class RecipeUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    instructions: str | None = Field(default=None, min_length=1)
    image_url: str | None = Field(default=None, max_length=2048)
    servings: int | None = Field(default=None, ge=1)
    tag_ids: list[int] | None = None
