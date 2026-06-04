from app.services.nutrition_parser import NutritionParser, NutritionInformation, NutritionValue


def test_parse_none_returns_none() -> None:
    assert NutritionParser.parse(None) is None


def test_parse_empty_dict_returns_empty() -> None:
    result = NutritionParser.parse({})
    assert result is not None
    assert result.calories is None
    assert result.carbohydrate_content is None
    assert result.extra == {}


def test_parse_calories_with_unit() -> None:
    result = NutritionParser.parse({"calories": "240 kcal"})
    assert result is not None
    assert result.calories is not None
    assert result.calories.value == 240.0
    assert result.calories.unit == "kcal"


def test_parse_calories_bare_number_uses_default_unit() -> None:
    result = NutritionParser.parse({"calories": "240"})
    assert result is not None
    assert result.calories is not None
    assert result.calories.value == 240.0
    assert result.calories.unit == "kcal"


def test_parse_carbohydrate_content_with_unit() -> None:
    result = NutritionParser.parse({"carbohydrateContent": "30 g"})
    assert result is not None
    assert result.carbohydrate_content is not None
    assert result.carbohydrate_content.value == 30.0
    assert result.carbohydrate_content.unit == "g"


def test_parse_protein_content_with_unit() -> None:
    result = NutritionParser.parse({"proteinContent": "15 g"})
    assert result is not None
    assert result.protein_content is not None
    assert result.protein_content.value == 15.0
    assert result.protein_content.unit == "g"


def test_parse_fat_content_with_unit() -> None:
    result = NutritionParser.parse({"fatContent": "8 g"})
    assert result is not None
    assert result.fat_content is not None
    assert result.fat_content.value == 8.0
    assert result.fat_content.unit == "g"


def test_parse_saturated_fat_content_with_unit() -> None:
    result = NutritionParser.parse({"saturatedFatContent": "3 g"})
    assert result is not None
    assert result.saturated_fat_content is not None
    assert result.saturated_fat_content.value == 3.0
    assert result.saturated_fat_content.unit == "g"


def test_parse_unsaturated_fat_content_with_unit() -> None:
    result = NutritionParser.parse({"unsaturatedFatContent": "4.5 g"})
    assert result is not None
    assert result.unsaturated_fat_content is not None
    assert result.unsaturated_fat_content.value == 4.5
    assert result.unsaturated_fat_content.unit == "g"


def test_parse_fiber_content_with_unit() -> None:
    result = NutritionParser.parse({"fiberContent": "2 g"})
    assert result is not None
    assert result.fiber_content is not None
    assert result.fiber_content.value == 2.0
    assert result.fiber_content.unit == "g"


def test_parse_sugar_content_with_unit() -> None:
    result = NutritionParser.parse({"sugarContent": "5 g"})
    assert result is not None
    assert result.sugar_content is not None
    assert result.sugar_content.value == 5.0
    assert result.sugar_content.unit == "g"


def test_parse_sodium_content_default_unit_mg() -> None:
    result = NutritionParser.parse({"sodiumContent": "500 mg"})
    assert result is not None
    assert result.sodium_content is not None
    assert result.sodium_content.value == 500.0
    assert result.sodium_content.unit == "mg"


def test_parse_sodium_content_bare_number_defaults_to_mg() -> None:
    result = NutritionParser.parse({"sodiumContent": "200"})
    assert result is not None
    assert result.sodium_content is not None
    assert result.sodium_content.value == 200.0
    assert result.sodium_content.unit == "mg"


def test_parse_cholesterol_content_default_unit_mg() -> None:
    result = NutritionParser.parse({"cholesterolContent": "30 mg"})
    assert result is not None
    assert result.cholesterol_content is not None
    assert result.cholesterol_content.value == 30.0
    assert result.cholesterol_content.unit == "mg"


def test_parse_serving_size_with_unit() -> None:
    result = NutritionParser.parse({"servingSize": "100 g"})
    assert result is not None
    assert result.serving_size is not None
    assert result.serving_size.value == 100.0
    assert result.serving_size.unit == "g"


def test_parse_trans_fat_content_with_unit() -> None:
    result = NutritionParser.parse({"transFatContent": "0.1 g"})
    assert result is not None
    assert result.trans_fat_content is not None
    assert result.trans_fat_content.value == 0.1
    assert result.trans_fat_content.unit == "g"


def test_parse_all_twelve_fields() -> None:
    result = NutritionParser.parse({
        "calories": "240 kcal",
        "carbohydrateContent": "30 g",
        "proteinContent": "15 g",
        "fatContent": "8 g",
        "saturatedFatContent": "3 g",
        "unsaturatedFatContent": "4.5 g",
        "fiberContent": "2 g",
        "sugarContent": "5 g",
        "sodiumContent": "500 mg",
        "cholesterolContent": "30 mg",
        "servingSize": "100 g",
        "transFatContent": "0.1 g",
    })
    assert result is not None
    assert result.calories.value == 240.0
    assert result.carbohydrate_content.value == 30.0
    assert result.protein_content.value == 15.0
    assert result.fat_content.value == 8.0
    assert result.saturated_fat_content.value == 3.0
    assert result.unsaturated_fat_content.value == 4.5
    assert result.fiber_content.value == 2.0
    assert result.sugar_content.value == 5.0
    assert result.sodium_content.value == 500.0
    assert result.cholesterol_content.value == 30.0
    assert result.serving_size.value == 100.0
    assert result.trans_fat_content.value == 0.1


def test_parse_missing_keys_leave_fields_as_none() -> None:
    result = NutritionParser.parse({"calories": "100 kcal"})
    assert result is not None
    assert result.carbohydrate_content is None
    assert result.protein_content is None
    assert result.fat_content is None


def test_parse_unknown_keys_passed_through_in_extra() -> None:
    result = NutritionParser.parse({"calories": "240 kcal", "vitaminD": "5 µg"})
    assert result is not None
    assert result.calories.value == 240.0
    assert result.extra == {"vitaminD": "5 µg"}


def test_parse_non_numeric_value_returns_none_for_field() -> None:
    result = NutritionParser.parse({"calories": "about 240"})
    assert result is not None
    assert result.calories is None


def test_parse_decimal_comma() -> None:
    result = NutritionParser.parse({"carbohydrateContent": "30,5 g"})
    assert result is not None
    assert result.carbohydrate_content is not None
    assert result.carbohydrate_content.value == 30.5
    assert result.carbohydrate_content.unit == "g"


def test_parse_negative_value() -> None:
    result = NutritionParser.parse({"calories": "-1 kcal"})
    assert result is not None
    assert result.calories.value == -1.0


def test_to_dict_serializes_all_fields() -> None:
    result = NutritionParser.parse({"calories": "240 kcal", "carbohydrateContent": "30 g"})
    assert result is not None
    d = result.to_dict()
    assert d == {
        "calories": {"value": 240.0, "unit": "kcal"},
        "carbohydrateContent": {"value": 30.0, "unit": "g"},
    }


def test_to_dict_omits_none_fields() -> None:
    result = NutritionParser.parse({"calories": "240 kcal"})
    assert result is not None
    d = result.to_dict()
    assert "carbohydrateContent" not in d
    assert d["calories"] == {"value": 240.0, "unit": "kcal"}


def test_to_dict_includes_extra() -> None:
    result = NutritionParser.parse({"calories": "240 kcal", "vitaminD": "5 µg"})
    assert result is not None
    d = result.to_dict()
    assert d["calories"] == {"value": 240.0, "unit": "kcal"}
    assert d["vitaminD"] == "5 µg"


def test_to_dict_returns_empty_dict_for_empty_input() -> None:
    result = NutritionParser.parse({})
    assert result is not None
    assert result.to_dict() == {}


def test_to_dict_returns_none_for_none_input() -> None:
    assert NutritionParser.parse(None) is None
