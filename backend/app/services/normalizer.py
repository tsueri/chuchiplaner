from difflib import SequenceMatcher

IngredientID = int


class IngredientNormalizer:
    def __init__(self, ingredients: dict[str, IngredientID]) -> None:
        self._ingredients = ingredients

    def resolve(
        self, scraped_name: str, household_aliases: dict[str, IngredientID]
    ) -> tuple[IngredientID | None, float]:
        name_lower = scraped_name.lower().strip()

        alias_lookup = {k.lower(): v for k, v in household_aliases.items()}
        if name_lower in alias_lookup:
            return alias_lookup[name_lower], 1.0

        ingredient_lookup = {k.lower(): v for k, v in self._ingredients.items()}
        if name_lower in ingredient_lookup:
            return ingredient_lookup[name_lower], 1.0

        best_match: IngredientID | None = None
        best_score = 0.0

        for name, ingredient_id in self._ingredients.items():
            score = SequenceMatcher(None, name_lower, name.lower()).ratio()
            if score > best_score:
                best_score = score
                best_match = ingredient_id

        if best_score < 0.6:
            return None, 0.0

        return best_match, round(best_score, 2)

    def learn_alias(
        self,
        aliases: dict[str, IngredientID],
        alias_name: str,
        ingredient_id: IngredientID,
    ) -> None:
        aliases[alias_name] = ingredient_id
