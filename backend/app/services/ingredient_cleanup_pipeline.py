from app.schemas.recipe import ScrapedIngredientItem
from app.services.ingredient_line_parser import IngredientLineParser
from app.services.ingredient_name_cleaner import IngredientNameCleaner
from app.services.normalizer import IngredientNormalizer


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
        items: list[ScrapedIngredientItem] = []
        for raw_line in raw_lines:
            parsed_line = IngredientLineParser.parse(raw_line)

            cleaned_name: str | None = None
            if parsed_line.name:
                cleaned_name = self._cleaner.clean(parsed_line.name)

            if parsed_line.quantity is not None and parsed_line.name:
                resolve_name: str = cleaned_name if cleaned_name else parsed_line.name
                resolved_id, confidence = self._normalizer.resolve(
                    resolve_name, household_aliases
                )
            else:
                resolved_id, confidence = None, 0.0

            items.append(
                ScrapedIngredientItem(
                    raw=raw_line,
                    name=parsed_line.name,
                    quantity=parsed_line.quantity,
                    unit=parsed_line.unit,
                    ingredient_id=resolved_id,
                    confidence=confidence,
                    tier1_cleaned_name=cleaned_name,
                )
            )

        return items
