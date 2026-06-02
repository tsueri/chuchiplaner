import pytest

from app.services.normalizer import IngredientNormalizer


@pytest.fixture
def ingredients() -> dict[str, int]:
    return {
        "Pouletbrust": 1,
        "Tomate": 2,
        "Zwiebel": 3,
        "Rahm": 4,
        "Mehl": 5,
    }


@pytest.fixture
def household_aliases() -> dict[str, int]:
    return {"Hähnchenbrust": 1, "Sahne": 4}


def test_exact_name_match(ingredients: dict[str, int]) -> None:
    normalizer = IngredientNormalizer(ingredients)
    match, confidence = normalizer.resolve("Pouletbrust", {})
    assert match == 1
    assert confidence == 1.0


def test_alias_match(
    ingredients: dict[str, int], household_aliases: dict[str, int]
) -> None:
    normalizer = IngredientNormalizer(ingredients)
    match, confidence = normalizer.resolve("Hähnchenbrust", household_aliases)
    assert match == 1
    assert confidence == 1.0


def test_fuzzy_match(ingredients: dict[str, int]) -> None:
    normalizer = IngredientNormalizer(ingredients)
    match, confidence = normalizer.resolve("Poulet", {})
    assert match == 1
    assert confidence < 1.0
    assert confidence > 0.0


def test_no_match(ingredients: dict[str, int]) -> None:
    normalizer = IngredientNormalizer(ingredients)
    match, confidence = normalizer.resolve("Koriander", {})
    assert match is None
    assert confidence == 0.0


def test_alias_takes_priority_over_fuzzy(
    ingredients: dict[str, int], household_aliases: dict[str, int]
) -> None:
    normalizer = IngredientNormalizer(ingredients)
    match, confidence = normalizer.resolve("Sahne", household_aliases)
    assert match == 4
    assert confidence == 1.0


def test_case_insensitive_exact(ingredients: dict[str, int]) -> None:
    normalizer = IngredientNormalizer(ingredients)
    match, confidence = normalizer.resolve("pouletbrust", {})
    assert match == 1
    assert confidence == 1.0


def test_case_insensitive_alias(
    ingredients: dict[str, int], household_aliases: dict[str, int]
) -> None:
    normalizer = IngredientNormalizer(ingredients)
    match, confidence = normalizer.resolve("hÄhnchenbrust", household_aliases)
    assert match == 1
    assert confidence == 1.0


def test_fuzzy_match_below_threshold_returns_none(
    ingredients: dict[str, int],
) -> None:
    normalizer = IngredientNormalizer(ingredients)
    match, confidence = normalizer.resolve("xyzxyz", {})
    assert match is None
    assert confidence == 0.0


def test_learn_alias_creates_mapping(ingredients: dict[str, int]) -> None:
    normalizer = IngredientNormalizer(ingredients)
    aliases: dict[str, int] = {}
    match, confidence = normalizer.resolve("Poulet", aliases)
    assert match == 1
    assert confidence < 1.0

    # Learning: user confirms the match → add alias
    normalizer.learn_alias(aliases, "Poulet", 1)
    assert aliases["Poulet"] == 1

    # Now resolve should find it via alias
    match, confidence = normalizer.resolve("Poulet", aliases)
    assert match == 1
    assert confidence == 1.0
