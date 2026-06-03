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
    }

    _QUANTITY_RE = re.compile(
        r"^(\d+(?:[.,]\d+)?)(?:\s*-\s*(\d+(?:[.,]\d+)?))?(.*)"
    )

    @staticmethod
    def parse(line: str) -> ParsedIngredientLine:
        stripped = line.strip()
        if not stripped:
            return ParsedIngredientLine(quantity=None, unit=None, name="")

        qmatch = IngredientLineParser._QUANTITY_RE.match(stripped)
        if not qmatch:
            return ParsedIngredientLine(
                quantity=None, unit=None, name=stripped
            )

        quantity = float(qmatch.group(1).replace(",", "."))
        rest = qmatch.group(3).strip()

        unit: str | None = None
        name: str = rest

        if rest:
            rest_clean = re.sub(r"^[,:]+\s*", "", rest)
            token_match = re.match(r"^([a-zA-ZäöüÄÖÜß]+)\s*(.*)", rest_clean)
            if token_match:
                token_raw = token_match.group(1)
                remaining = token_match.group(2).strip()
                remaining = re.sub(r"^[,:]+\s*", "", remaining)

                canonical = IngredientLineParser.UNIT_SYNONYMS.get(
                    token_raw.lower()
                )
                if canonical:
                    unit = canonical
                    name = remaining if remaining else ""
                else:
                    name = rest_clean

        return ParsedIngredientLine(quantity=quantity, unit=unit, name=name)
