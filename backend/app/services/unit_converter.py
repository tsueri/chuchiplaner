class UnitConverter:
    GRAM_UNITS: dict[str, int] = {
        "g": 1,
        "kg": 1000,
    }

    ML_UNITS: dict[str, int] = {
        "ml": 1,
        "l": 1000,
        "el": 15,
        "tl": 5,
    }

    PIECE_UNITS: set[str] = {"st\u00fcck", "bund", "prise"}

    @staticmethod
    def normalize(
        amount: float, unit: str
    ) -> tuple[float | None, float | None, float | None]:
        unit_clean = unit.strip().lower()

        if unit_clean in UnitConverter.GRAM_UNITS:
            return (amount * UnitConverter.GRAM_UNITS[unit_clean], None, None)

        if unit_clean in UnitConverter.ML_UNITS:
            return (None, amount * UnitConverter.ML_UNITS[unit_clean], None)

        if unit_clean in UnitConverter.PIECE_UNITS:
            return (None, None, amount)

        return (None, None, None)
