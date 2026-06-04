from app.services.ingredient_line_parser import (
    IngredientLineParser,
    ParsedIngredientLine,
)


def test_parse_simple_number_unit_name() -> None:
    result = IngredientLineParser.parse("600g Kalbfleisch")
    assert result == ParsedIngredientLine(
        quantity=600.0, unit="g", name="Kalbfleisch"
    )


def test_parse_decimal_with_space_before_unit() -> None:
    result = IngredientLineParser.parse("1.5 kg Kartoffeln, gew\u00fcrfelt")
    assert result == ParsedIngredientLine(
        quantity=1.5, unit="kg", name="Kartoffeln, gew\u00fcrfelt"
    )


def test_parse_number_without_unit() -> None:
    result = IngredientLineParser.parse("1 Zwiebel, gehackt")
    assert result == ParsedIngredientLine(
        quantity=1.0, unit=None, name="Zwiebel, gehackt"
    )


def test_parse_range_collapses_to_lower_bound() -> None:
    result = IngredientLineParser.parse("2-3 EL Oliven\u00f6l")
    assert result == ParsedIngredientLine(
        quantity=2.0, unit="EL", name="Oliven\u00f6l"
    )


def test_parse_no_number() -> None:
    result = IngredientLineParser.parse("Salz und Pfeffer")
    assert result == ParsedIngredientLine(
        quantity=None, unit=None, name="Salz und Pfeffer"
    )


def test_parse_pure_qualifier_word() -> None:
    result = IngredientLineParser.parse("nach Belieben")
    assert result == ParsedIngredientLine(
        quantity=None, unit=None, name="nach Belieben"
    )


def test_parse_etwas() -> None:
    result = IngredientLineParser.parse("etwas Oliven\u00f6l")
    assert result == ParsedIngredientLine(
        quantity=None, unit=None, name="etwas Oliven\u00f6l"
    )


def test_parse_unit_with_space_after_number() -> None:
    result = IngredientLineParser.parse("200 ml Rahm")
    assert result == ParsedIngredientLine(
        quantity=200.0, unit="ml", name="Rahm"
    )


def test_parse_decimal_with_comma() -> None:
    result = IngredientLineParser.parse("0,5 l Bier")
    assert result == ParsedIngredientLine(
        quantity=0.5, unit="l", name="Bier"
    )


def test_parse_unit_stuck() -> None:
    result = IngredientLineParser.parse("3 St\u00fcck Eier")
    assert result == ParsedIngredientLine(
        quantity=3.0, unit="St\u00fcck", name="Eier"
    )


def test_parse_bund() -> None:
    result = IngredientLineParser.parse("1 Bund Petersilie")
    assert result == ParsedIngredientLine(
        quantity=1.0, unit="Bund", name="Petersilie"
    )


def test_parse_prise() -> None:
    result = IngredientLineParser.parse("1 Prise Salz")
    assert result == ParsedIngredientLine(
        quantity=1.0, unit="Prise", name="Salz"
    )


def test_parse_dose() -> None:
    result = IngredientLineParser.parse("1 Dose Tomaten")
    assert result == ParsedIngredientLine(
        quantity=1.0, unit="Dose", name="Tomaten"
    )


def test_parse_becher() -> None:
    result = IngredientLineParser.parse("1 Becher Joghurt")
    assert result == ParsedIngredientLine(
        quantity=1.0, unit="Becher", name="Joghurt"
    )


def test_parse_packung() -> None:
    result = IngredientLineParser.parse("1 Packung Spaghetti")
    assert result == ParsedIngredientLine(
        quantity=1.0, unit="Packung", name="Spaghetti"
    )


def test_parse_scheibe() -> None:
    result = IngredientLineParser.parse("2 Scheiben Brot")
    assert result == ParsedIngredientLine(
        quantity=2.0, unit="Scheibe", name="Brot"
    )


def test_parse_essloffel_synonym() -> None:
    result = IngredientLineParser.parse("1 Essl\u00f6ffel Oliven\u00f6l")
    assert result == ParsedIngredientLine(
        quantity=1.0, unit="EL", name="Oliven\u00f6l"
    )


def test_parse_teeloffel_synonym() -> None:
    result = IngredientLineParser.parse("1 Teel\u00f6ffel Salz")
    assert result == ParsedIngredientLine(
        quantity=1.0, unit="TL", name="Salz"
    )


def test_parse_stk_synonym() -> None:
    result = IngredientLineParser.parse("2 Stk Karotten")
    assert result == ParsedIngredientLine(
        quantity=2.0, unit="St\u00fcck", name="Karotten"
    )


def test_parse_gramm_synonym() -> None:
    result = IngredientLineParser.parse("500 Gramm Mehl")
    assert result == ParsedIngredientLine(
        quantity=500.0, unit="g", name="Mehl"
    )


def test_parse_ml_lowercase_unit() -> None:
    result = IngredientLineParser.parse("100ml Rahm")
    assert result == ParsedIngredientLine(
        quantity=100.0, unit="ml", name="Rahm"
    )


def test_parse_unit_no_space_after_number() -> None:
    result = IngredientLineParser.parse("250g Butter")
    assert result == ParsedIngredientLine(
        quantity=250.0, unit="g", name="Butter"
    )


def test_parse_el_lowercase_synonym() -> None:
    result = IngredientLineParser.parse("2 el \u00d6l")
    assert result == ParsedIngredientLine(
        quantity=2.0, unit="EL", name="\u00d6l"
    )


def test_parse_tl_synonym() -> None:
    result = IngredientLineParser.parse("1 TL Zucker")
    assert result == ParsedIngredientLine(
        quantity=1.0, unit="TL", name="Zucker"
    )


def test_parse_empty_string() -> None:
    result = IngredientLineParser.parse("")
    assert result == ParsedIngredientLine(
        quantity=None, unit=None, name=""
    )


def test_parse_only_whitespace() -> None:
    result = IngredientLineParser.parse("   ")
    assert result == ParsedIngredientLine(
        quantity=None, unit=None, name=""
    )


def test_parse_leading_and_trailing_whitespace() -> None:
    result = IngredientLineParser.parse("  300g Mehl  ")
    assert result == ParsedIngredientLine(
        quantity=300.0, unit="g", name="Mehl"
    )


def test_parse_number_with_colon_separator() -> None:
    result = IngredientLineParser.parse("1: Zwiebel")
    assert result == ParsedIngredientLine(
        quantity=1.0, unit=None, name="Zwiebel"
    )


def test_parse_range_no_space_around_dash() -> None:
    result = IngredientLineParser.parse("2-3EL Honig")
    assert result == ParsedIngredientLine(
        quantity=2.0, unit="EL", name="Honig"
    )


def test_parse_unicode_fraction_half() -> None:
    result = IngredientLineParser.parse("\u00bd EL fl\u00fcssiger Honig")
    assert result == ParsedIngredientLine(
        quantity=0.5, unit="EL", name="fl\u00fcssiger Honig"
    )


def test_parse_compound_quantity_with_fraction() -> None:
    result = IngredientLineParser.parse("1 \u00bc TL Salz")
    assert result == ParsedIngredientLine(
        quantity=1.25, unit="TL", name="Salz"
    )


def test_parse_msp_with_dot() -> None:
    result = IngredientLineParser.parse("2 Msp. Muskat")
    assert result == ParsedIngredientLine(
        quantity=2.0, unit="Msp", name="Muskat"
    )


def test_parse_deciliter() -> None:
    result = IngredientLineParser.parse("5 dl Milchwasser")
    assert result == ParsedIngredientLine(
        quantity=5.0, unit="ml", name="Milchwasser"
    )


def test_parse_deciliter_rotwein() -> None:
    result = IngredientLineParser.parse("1 dl Rotwein")
    assert result == ParsedIngredientLine(
        quantity=1.0, unit="ml", name="Rotwein"
    )


def test_parse_quarter_fraction() -> None:
    result = IngredientLineParser.parse("\u00be l Wasser")
    assert result == ParsedIngredientLine(
        quantity=0.75, unit="l", name="Wasser"
    )
