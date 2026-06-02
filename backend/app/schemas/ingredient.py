from pydantic import BaseModel, Field


class IngredientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class IngredientResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class IngredientAliasCreate(BaseModel):
    ingredient_id: int
    alias_name: str = Field(min_length=1, max_length=255)


class IngredientAliasResponse(BaseModel):
    id: int
    household_id: int
    alias_name: str
    ingredient_id: int

    model_config = {"from_attributes": True}
