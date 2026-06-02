
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
