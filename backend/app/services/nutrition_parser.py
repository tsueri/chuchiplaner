from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NutritionValue:
    value: float
    unit: str


@dataclass
class NutritionInformation:
    calories: NutritionValue | None = None
    carbohydrate_content: NutritionValue | None = None
    protein_content: NutritionValue | None = None
    fat_content: NutritionValue | None = None
    saturated_fat_content: NutritionValue | None = None
    unsaturated_fat_content: NutritionValue | None = None
    fiber_content: NutritionValue | None = None
    sugar_content: NutritionValue | None = None
    sodium_content: NutritionValue | None = None
    cholesterol_content: NutritionValue | None = None
    serving_size: NutritionValue | None = None
    trans_fat_content: NutritionValue | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = dict(self.extra)
        field_map = {
            "calories": "calories",
            "carbohydrate_content": "carbohydrateContent",
            "protein_content": "proteinContent",
            "fat_content": "fatContent",
            "saturated_fat_content": "saturatedFatContent",
            "unsaturated_fat_content": "unsaturatedFatContent",
            "fiber_content": "fiberContent",
            "sugar_content": "sugarContent",
            "sodium_content": "sodiumContent",
            "cholesterol_content": "cholesterolContent",
            "serving_size": "servingSize",
            "trans_fat_content": "transFatContent",
        }
        for attr, key in field_map.items():
            val = getattr(self, attr)
            if val is not None:
                result[key] = {"value": val.value, "unit": val.unit}
        return result


class NutritionParser:
    KEY_MAP: dict[str, str] = {
        "calories": "calories",
        "carbohydrateContent": "carbohydrate_content",
        "proteinContent": "protein_content",
        "fatContent": "fat_content",
        "saturatedFatContent": "saturated_fat_content",
        "unsaturatedFatContent": "unsaturated_fat_content",
        "fiberContent": "fiber_content",
        "sugarContent": "sugar_content",
        "sodiumContent": "sodium_content",
        "cholesterolContent": "cholesterol_content",
        "servingSize": "serving_size",
        "transFatContent": "trans_fat_content",
    }

    DEFAULT_UNITS: dict[str, str] = {
        "calories": "kcal",
        "carbohydrateContent": "g",
        "proteinContent": "g",
        "fatContent": "g",
        "saturatedFatContent": "g",
        "unsaturatedFatContent": "g",
        "fiberContent": "g",
        "sugarContent": "g",
        "sodiumContent": "mg",
        "cholesterolContent": "mg",
        "servingSize": "g",
        "transFatContent": "g",
    }

    _VALUE_PATTERN = re.compile(r"^(-?\d+(?:[.,]\d+)?)\s*(\S+)?$")

    @staticmethod
    def parse(nutrients: dict[str, Any] | None) -> NutritionInformation | None:
        if nutrients is None:
            return None

        info = NutritionInformation()
        for key, raw_value in nutrients.items():
            attr = NutritionParser.KEY_MAP.get(key)
            if attr is None:
                info.extra[key] = raw_value
                continue

            if not isinstance(raw_value, str):
                continue

            match = NutritionParser._VALUE_PATTERN.match(raw_value.strip())
            if match is None:
                continue

            try:
                num = float(match.group(1).replace(",", "."))
            except ValueError:
                continue

            unit = match.group(2)
            if unit is None:
                unit = NutritionParser.DEFAULT_UNITS.get(key, "")

            setattr(info, attr, NutritionValue(value=num, unit=unit))

        return info
