from typing import Any


class UnitConverter:
    GRAM_UNITS: dict[str, int] = {
        "g": 1,
        "kg": 1000,
    }

    ML_UNITS: dict[str, int] = {
        "ml": 1,
        "dl": 100,
        "l": 1000,
        "el": 15,
        "tl": 5,
    }

    PIECE_UNITS: set[str] = {"st\u00fcck", "bund", "prise", "msp"}

    _SPOON_UNIT_ATTR_SUFFIX: dict[str, str] = {
        "el": "el",
        "tl": "tl",
        "msp": "msp",
        "prise": "pris",
    }

    @staticmethod
    def normalize(
        amount: float, unit: str, ingredient: Any = None
    ) -> tuple[float | None, float | None, float | None]:
        unit_clean = unit.strip().lower()

        if unit_clean in UnitConverter.GRAM_UNITS:
            return (amount * UnitConverter.GRAM_UNITS[unit_clean], None, None)

        spoon_units = UnitConverter._SPOON_UNIT_ATTR_SUFFIX
        if ingredient is not None and unit_clean in spoon_units:
            attr = spoon_units[unit_clean]
            grams_per = getattr(ingredient, f"grams_per_{attr}", None)
            if grams_per is not None:
                return (amount * float(grams_per), None, None)
            ml_per = getattr(ingredient, f"ml_per_{attr}", None)
            if ml_per is not None:
                return (None, amount * float(ml_per), None)

        if unit_clean in UnitConverter.ML_UNITS:
            return (None, amount * UnitConverter.ML_UNITS[unit_clean], None)

        if unit_clean in UnitConverter.PIECE_UNITS:
            return (None, None, amount)

        return (None, None, None)
