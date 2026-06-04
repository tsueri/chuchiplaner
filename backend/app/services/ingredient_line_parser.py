from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedIngredientLine:
    quantity: float | None
    unit: str | None
    name: str


class IngredientLineParser:
    UNIT_SYNONYMS: dict[str, str] = {
        "g": "g",
        "gramm": "g",
        "kg": "kg",
        "kilogramm": "kg",
        "ml": "ml",
        "milliliter": "ml",
        "l": "l",
        "liter": "l",
        "dl": "ml",
        "el": "EL",
        "esslöffel": "EL",
        "essloffel": "EL",
        "tl": "TL",
        "teelöffel": "TL",
        "teeloffel": "TL",
        "stück": "Stück",
        "stuck": "Stück",
        "stk": "Stück",
        "bund": "Bund",
        "prise": "Prise",
        "dose": "Dose",
        "becher": "Becher",
        "packung": "Packung",
        "scheibe": "Scheibe",
        "scheiben": "Scheibe",
        "msp": "Msp",
    }

    _UNICODE_FRACTIONS: dict[str, float] = {
        "\u00bd": 0.5,
        "\u2153": 1 / 3,
        "\u2154": 2 / 3,
        "\u00bc": 0.25,
        "\u00be": 0.75,
        "\u2155": 0.2,
        "\u2156": 0.4,
        "\u2157": 0.6,
        "\u2158": 0.8,
        "\u2159": 1 / 6,
        "\u215a": 5 / 6,
        "\u215b": 0.125,
        "\u215c": 0.375,
        "\u215d": 0.625,
        "\u215e": 0.875,
    }

    _QUANTITY_RE = re.compile(
        r"^(\d+(?:[.,]\d+)?)(?:\s*-\s*(\d+(?:[.,]\d+)?))?(.*)"
    )

    _FRACTION_LEADING_RE = re.compile(
        r"^([\u00bc-\u00be\u2153-\u215e])(.*)"
    )

    @staticmethod
    def parse(line: str) -> ParsedIngredientLine:
        stripped = line.strip()
        if not stripped:
            return ParsedIngredientLine(quantity=None, unit=None, name="")

        qmatch = IngredientLineParser._QUANTITY_RE.match(stripped)
        if not qmatch:
            frac_match = IngredientLineParser._FRACTION_LEADING_RE.match(stripped)
            if frac_match:
                quantity = IngredientLineParser._UNICODE_FRACTIONS[frac_match.group(1)]
                rest = frac_match.group(2).strip()
            else:
                return ParsedIngredientLine(
                    quantity=None, unit=None, name=stripped
                )
        else:
            quantity = float(qmatch.group(1).replace(",", "."))
            rest = qmatch.group(3).strip()

            frac_match = IngredientLineParser._FRACTION_LEADING_RE.match(rest)
            if frac_match:
                quantity += IngredientLineParser._UNICODE_FRACTIONS[
                    frac_match.group(1)
                ]
                rest = frac_match.group(2).strip()

        unit: str | None = None
        name: str = rest

        if rest:
            rest_clean = re.sub(r"^[,:]+\s*", "", rest)
            token_match = re.match(r"^([a-zA-ZäöüÄÖÜß]+\.?)\s*(.*)", rest_clean)
            if token_match:
                token_raw = token_match.group(1)
                remaining = token_match.group(2).strip()
                remaining = re.sub(r"^[,:]+\s*", "", remaining)

                token_clean = token_raw.rstrip(".")
                canonical = IngredientLineParser.UNIT_SYNONYMS.get(
                    token_clean.lower()
                )
                if canonical:
                    unit = canonical
                    name = remaining if remaining else ""
                else:
                    name = rest_clean

        return ParsedIngredientLine(quantity=quantity, unit=unit, name=name)
