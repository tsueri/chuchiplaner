from __future__ import annotations

import logging
import re

from app.schemas.recipe import ScrapedIngredientItem
from app.services.ingredient_line_parser import IngredientLineParser
from app.services.ingredient_name_cleaner import IngredientNameCleaner
from app.services.normalizer import IngredientNormalizer

logger = logging.getLogger("chuchiplaner")

_EQUIPMENT_DENYLIST: set[str] = {
    "backpapier", "backform", "backblech", "blech",
    "pfanne", "kochtopf", "topf", "schüssel", "schuessel",
    "schale", "form", "folie", "deckel", "sieb", "tuch",
    "teller", "gabel", "löffel", "loffel", "messer",
    "becher", "glas",
}


def _post_process_name(name: str) -> tuple[str, bool]:
    """Apply regex rules to clean an ingredient name after NER.

    Returns (cleaned_name, is_equipment).
    """
    result = name.strip()

    # Strip "oder Y" alternatives
    result = re.sub(r'\s+oder\s+.+$', '', result, flags=re.IGNORECASE)

    # Strip "à Ng" / "a Ng" embedded weight specs
    result = re.sub(r'\s+[àa]\s+\d+\s*g\b', '', result, flags=re.IGNORECASE)

    # Strip parentheticals "(X)"
    result = re.sub(r'\s*\([^)]*\)', '', result)

    # Strip trailing prep notes: ", X" (e.g. ", in Sticks geschnitten", ", gehackt")
    result = re.sub(r'\s*,\s+[^,]*$', '', result)

    # Strip slash-delimited alternatives "X / Y" → keep X
    result = re.sub(r'\s*/\s*.+$', '', result)

    # Equipment detection: if any denylist word is a substring of any word
    words_lower = result.lower()
    is_equipment = any(equip in words_lower for equip in _EQUIPMENT_DENYLIST)

    return result.strip(), is_equipment


class IngredientCleanupPipeline:
    def __init__(
        self,
        name_cleaner: IngredientNameCleaner,
        normalizer: IngredientNormalizer,
    ) -> None:
        self._cleaner = name_cleaner
        self._normalizer = normalizer

    def process(
        self,
        raw_lines: list[str],
        household_aliases: dict[str, int],
    ) -> list[ScrapedIngredientItem]:
        logger.debug("Pipeline processing %d raw lines", len(raw_lines))
        items: list[ScrapedIngredientItem] = []
        for raw_line in raw_lines:
            parsed_line = IngredientLineParser.parse(raw_line)

            cleaned_name: str | None = None
            if parsed_line.name:
                ner_cleaned = self._cleaner.clean(parsed_line.name)
                post_cleaned, is_equipment = _post_process_name(ner_cleaned)
                cleaned_name = post_cleaned
                if cleaned_name != parsed_line.name:
                    logger.debug(
                        "Tier1 cleaned: %r → %r", parsed_line.name, cleaned_name
                    )
            else:
                is_equipment = False

            display_name: str = cleaned_name if cleaned_name else parsed_line.name

            if parsed_line.quantity is not None and parsed_line.name:
                resolve_name: str = cleaned_name if cleaned_name else parsed_line.name
                resolved_id, confidence = self._normalizer.resolve(
                    resolve_name, household_aliases
                )
                logger.debug(
                    "Normalizer resolved %r → id=%s confidence=%s",
                    resolve_name,
                    resolved_id,
                    confidence,
                )
            else:
                resolved_id, confidence = None, 0.0

            items.append(
                ScrapedIngredientItem(
                    raw=raw_line,
                    name=display_name,
                    quantity=parsed_line.quantity,
                    unit=parsed_line.unit,
                    ingredient_id=resolved_id,
                    confidence=confidence,
                    tier1_cleaned_name=cleaned_name,
                    is_equipment=is_equipment,
                )
            )

        return items
