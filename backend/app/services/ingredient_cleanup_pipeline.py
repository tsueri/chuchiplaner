from __future__ import annotations

from typing import TYPE_CHECKING

from app.schemas.recipe import ScrapedIngredientItem
from app.services.ingredient_line_parser import IngredientLineParser
from app.services.ingredient_name_cleaner import IngredientNameCleaner
from app.services.normalizer import IngredientNormalizer

if TYPE_CHECKING:
    from app.services.ingredient_llm_resolver import IngredientLLMResolver


class IngredientCleanupPipeline:
    def __init__(
        self,
        name_cleaner: IngredientNameCleaner,
        normalizer: IngredientNormalizer,
        llm_resolver: IngredientLLMResolver | None = None,
    ) -> None:
        self._cleaner = name_cleaner
        self._normalizer = normalizer
        self._llm_resolver = llm_resolver

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

            display_name: str = cleaned_name if cleaned_name else parsed_line.name

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
                    name=display_name,
                    quantity=parsed_line.quantity,
                    unit=parsed_line.unit,
                    ingredient_id=resolved_id,
                    confidence=confidence,
                    tier1_cleaned_name=cleaned_name,
                )
            )

        if self._llm_resolver is not None:
            from app.services.ingredient_llm_resolver import IngredientLLMResolver

            hard_items: list[tuple[int, ScrapedIngredientItem]] = []
            for idx, item in enumerate(items):
                if IngredientLLMResolver.needs_tier2(item):
                    hard_items.append((idx, item))

            if hard_items:
                hard_only = [item for _, item in hard_items]
                tier2_results = self._llm_resolver.resolve_batch(
                    hard_only, self._normalizer._ingredients
                )
                for (idx, item), result in zip(hard_items, tier2_results):
                    items[idx] = IngredientLLMResolver.apply_tier2_result(
                        item, result
                    )
                    t2_name = items[idx].tier2_cleaned_name
                    if t2_name:
                        items[idx].name = t2_name

        return items
