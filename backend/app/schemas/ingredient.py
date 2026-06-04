from typing import Optional

from pydantic import BaseModel, Field, model_validator


class IngredientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class IngredientResponse(BaseModel):
    id: int
    name: str
    grams_per_el: Optional[float] = None
    ml_per_el: Optional[float] = None
    grams_per_tl: Optional[float] = None
    ml_per_tl: Optional[float] = None
    grams_per_msp: Optional[float] = None
    ml_per_msp: Optional[float] = None
    grams_per_pris: Optional[float] = None
    ml_per_pris: Optional[float] = None

    model_config = {"from_attributes": True}


class IngredientUpdate(BaseModel):
    grams_per_el: Optional[float] = None
    ml_per_el: Optional[float] = None
    grams_per_tl: Optional[float] = None
    ml_per_tl: Optional[float] = None
    grams_per_msp: Optional[float] = None
    ml_per_msp: Optional[float] = None
    grams_per_pris: Optional[float] = None
    ml_per_pris: Optional[float] = None

    @model_validator(mode="after")
    def validate_mutual_exclusivity(self) -> "IngredientUpdate":
        pairs = [
            ("grams_per_el", "ml_per_el"),
            ("grams_per_tl", "ml_per_tl"),
            ("grams_per_msp", "ml_per_msp"),
            ("grams_per_pris", "ml_per_pris"),
        ]
        for grams_field, ml_field in pairs:
            grams_val = getattr(self, grams_field)
            ml_val = getattr(self, ml_field)
            if grams_val is not None and ml_val is not None:
                raise ValueError(
                    f"{grams_field} and {ml_field} cannot both be set"
                )
        return self


class IngredientAliasCreate(BaseModel):
    ingredient_id: int
    alias_name: str = Field(min_length=1, max_length=255)


class IngredientAliasResponse(BaseModel):
    id: int
    household_id: int
    alias_name: str
    ingredient_id: int

    model_config = {"from_attributes": True}
