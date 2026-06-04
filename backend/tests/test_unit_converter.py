
from app.services.unit_converter import UnitConverter


def test_grams() -> None:
    result = UnitConverter.normalize(200, "g")
    assert result == (200, None, None)


def test_kilograms_to_grams() -> None:
    result = UnitConverter.normalize(1.5, "kg")
    assert result == (1500, None, None)


def test_milliliters() -> None:
    result = UnitConverter.normalize(100, "ml")
    assert result == (None, 100, None)


def test_liters_to_milliliters() -> None:
    result = UnitConverter.normalize(0.5, "l")
    assert result == (None, 500, None)


def test_essloeffel_to_milliliters() -> None:
    result = UnitConverter.normalize(2, "EL")
    assert result == (None, 30, None)


def test_teeloeffel_to_milliliters() -> None:
    result = UnitConverter.normalize(3, "TL")
    assert result == (None, 15, None)


def test_stueck() -> None:
    result = UnitConverter.normalize(4, "Stück")
    assert result == (None, None, 4)


def test_bund() -> None:
    result = UnitConverter.normalize(1, "Bund")
    assert result == (None, None, 1)


def test_prise_to_one_piece() -> None:
    result = UnitConverter.normalize(2, "Prise")
    assert result == (None, None, 2)


def test_zero_amount() -> None:
    result = UnitConverter.normalize(0, "g")
    assert result == (0, None, None)


def test_negative_amount() -> None:
    result = UnitConverter.normalize(-100, "g")
    assert result == (-100, None, None)


def test_unknown_unit_returns_none() -> None:
    result = UnitConverter.normalize(5, "Tasse")
    assert result == (None, None, None)


def test_case_insensitive_unit() -> None:
    result = UnitConverter.normalize(250, "G")
    assert result == (250, None, None)


def test_whitespace_insensitive_unit() -> None:
    result = UnitConverter.normalize(1, "  kg  ")
    assert result == (1000, None, None)


class _FakeIngredient:
    def __init__(
        self,
        grams_per_el: float | None = None,
        ml_per_el: float | None = None,
        grams_per_tl: float | None = None,
        ml_per_tl: float | None = None,
        grams_per_msp: float | None = None,
        ml_per_msp: float | None = None,
        grams_per_pris: float | None = None,
        ml_per_pris: float | None = None,
    ):
        self.grams_per_el = grams_per_el
        self.ml_per_el = ml_per_el
        self.grams_per_tl = grams_per_tl
        self.ml_per_tl = ml_per_tl
        self.grams_per_msp = grams_per_msp
        self.ml_per_msp = ml_per_msp
        self.grams_per_pris = grams_per_pris
        self.ml_per_pris = ml_per_pris


def test_el_with_grams_per_el_returns_grams() -> None:
    ingredient = _FakeIngredient(grams_per_el=10)
    result = UnitConverter.normalize(2, "EL", ingredient=ingredient)
    assert result == (20, None, None)


def test_tl_with_ml_per_tl_returns_ml() -> None:
    ingredient = _FakeIngredient(ml_per_tl=5)
    result = UnitConverter.normalize(1, "TL", ingredient=ingredient)
    assert result == (None, 5, None)


def test_msp_with_grams_per_msp_returns_grams() -> None:
    ingredient = _FakeIngredient(grams_per_msp=2)
    result = UnitConverter.normalize(3, "MSP", ingredient=ingredient)
    assert result == (6, None, None)


def test_prise_with_ml_per_pris_returns_ml() -> None:
    ingredient = _FakeIngredient(ml_per_pris=3)
    result = UnitConverter.normalize(2, "Prise", ingredient=ingredient)
    assert result == (None, 6, None)


def test_el_grams_takes_precedence_over_ml() -> None:
    ingredient = _FakeIngredient(grams_per_el=10, ml_per_el=15)
    result = UnitConverter.normalize(2, "EL", ingredient=ingredient)
    assert result == (20, None, None)


def test_el_without_conversions_falls_back_to_ml() -> None:
    ingredient = _FakeIngredient()
    result = UnitConverter.normalize(1, "EL", ingredient=ingredient)
    assert result == (None, 15, None)


def test_msp_without_conversions_falls_back_to_pieces() -> None:
    ingredient = _FakeIngredient()
    result = UnitConverter.normalize(1, "MSP", ingredient=ingredient)
    assert result == (None, None, 1)


def test_el_without_ingredient_is_backward_compatible() -> None:
    result = UnitConverter.normalize(1, "EL")
    assert result == (None, 15, None)


def test_msp_without_ingredient_is_backward_compatible() -> None:
    result = UnitConverter.normalize(1, "MSP")
    assert result == (None, None, 1)


def test_g_with_ingredient_unchanged() -> None:
    ingredient = _FakeIngredient(grams_per_el=10)
    result = UnitConverter.normalize(200, "g", ingredient=ingredient)
    assert result == (200, None, None)


def test_kg_with_ingredient_unchanged() -> None:
    ingredient = _FakeIngredient(grams_per_el=10)
    result = UnitConverter.normalize(1.5, "kg", ingredient=ingredient)
    assert result == (1500, None, None)


def test_ml_with_ingredient_unchanged() -> None:
    ingredient = _FakeIngredient(ml_per_el=15)
    result = UnitConverter.normalize(100, "ml", ingredient=ingredient)
    assert result == (None, 100, None)


def test_l_with_ingredient_unchanged() -> None:
    ingredient = _FakeIngredient(ml_per_el=15)
    result = UnitConverter.normalize(0.5, "l", ingredient=ingredient)
    assert result == (None, 500, None)


def test_stueck_with_ingredient_unchanged() -> None:
    ingredient = _FakeIngredient(grams_per_el=10)
    result = UnitConverter.normalize(4, "Stück", ingredient=ingredient)
    assert result == (None, None, 4)


def test_bund_with_ingredient_unchanged() -> None:
    ingredient = _FakeIngredient(grams_per_el=10)
    result = UnitConverter.normalize(1, "Bund", ingredient=ingredient)
    assert result == (None, None, 1)


def test_tl_with_ml_and_grams_prefers_grams() -> None:
    ingredient = _FakeIngredient(grams_per_tl=3, ml_per_tl=5)
    result = UnitConverter.normalize(2, "TL", ingredient=ingredient)
    assert result == (6, None, None)


def test_prise_with_grams_per_pris_returns_grams() -> None:
    ingredient = _FakeIngredient(grams_per_pris=1)
    result = UnitConverter.normalize(3, "Prise", ingredient=ingredient)
    assert result == (3, None, None)


def test_msp_with_ml_and_grams_prefers_grams() -> None:
    ingredient = _FakeIngredient(grams_per_msp=2, ml_per_msp=4)
    result = UnitConverter.normalize(1, "MSP", ingredient=ingredient)
    assert result == (2, None, None)
