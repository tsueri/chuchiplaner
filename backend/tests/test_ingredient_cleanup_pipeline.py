from app.services.ingredient_cleanup_pipeline import IngredientCleanupPipeline
from app.services.normalizer import IngredientNormalizer


class _FakeCleaner:
    def clean(self, name: str) -> str:
        # Simple mock: return last word as ingredient name
        words = name.replace(",", "").split()
        return words[-1] if words else name


class TestIngredientCleanupPipeline:
    def test_process_basic_ingredients(self) -> None:
        cleaner = _FakeCleaner()
        ingredients_map = {"Kalbfleisch": 1, "Rahm": 2}
        normalizer = IngredientNormalizer(ingredients_map)
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        raw_lines = ["600g Kalbfleisch", "200ml Rahm"]
        result = pipeline.process(raw_lines, {})

        assert len(result) == 2

        assert result[0].raw == "600g Kalbfleisch"
        assert result[0].name == "Kalbfleisch"
        assert result[0].quantity == 600.0
        assert result[0].unit == "g"
        assert result[0].tier1_cleaned_name == "Kalbfleisch"
        assert result[0].ingredient_id == 1
        assert result[0].confidence == 1.0

        assert result[1].raw == "200ml Rahm"
        assert result[1].name == "Rahm"
        assert result[1].quantity == 200.0
        assert result[1].unit == "ml"
        assert result[1].tier1_cleaned_name == "Rahm"
        assert result[1].ingredient_id == 2
        assert result[1].confidence == 1.0

    def test_process_with_adjectives_stripped(self) -> None:
        cleaner = _FakeCleaner()
        ingredients_map = {"Spargeln": 1}
        normalizer = IngredientNormalizer(ingredients_map)
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        raw_lines = ["500g grüne Spargeln, in Stücken"]
        result = pipeline.process(raw_lines, {})

        assert len(result) == 1
        assert result[0].raw == "500g grüne Spargeln, in Stücken"
        assert result[0].name == "grüne Spargeln, in Stücken"  # parser output
        assert result[0].tier1_cleaned_name == "Stücken"

    def test_tier1_cleaned_name_set_on_every_item(self) -> None:
        cleaner = _FakeCleaner()
        ingredients_map = {"Rahm": 1}
        normalizer = IngredientNormalizer(ingredients_map)
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        raw_lines = ["200ml Rahm"]
        result = pipeline.process(raw_lines, {})

        assert result[0].tier1_cleaned_name is not None

    def test_pipeline_uses_cleaned_name_for_resolution(self) -> None:
        cleaner = _FakeCleaner()
        ingredients_map = {"Spargeln": 1}
        normalizer = IngredientNormalizer(ingredients_map)
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        raw_lines = ["500g grüne Spargeln"]
        result = pipeline.process(raw_lines, {})

        # The fake cleaner returns "Spargeln" (last word)
        # The normalizer should match "Spargeln" → ingredient_id 1
        assert result[0].ingredient_id == 1
        assert result[0].confidence == 1.0

    def test_pipeline_handles_unmatched_line(self) -> None:
        cleaner = _FakeCleaner()
        ingredients_map: dict[str, int] = {}
        normalizer = IngredientNormalizer(ingredients_map)
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        raw_lines = ["etwas Salz"]
        result = pipeline.process(raw_lines, {})

        assert len(result) == 1
        assert result[0].name == "etwas Salz"
        assert result[0].tier1_cleaned_name == "Salz"
        assert result[0].ingredient_id is None
        assert result[0].confidence == 0.0

    def test_pipeline_empty_name_line(self) -> None:
        cleaner = _FakeCleaner()
        ingredients_map: dict[str, int] = {}
        normalizer = IngredientNormalizer(ingredients_map)
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        raw_lines = ["etwas"]
        result = pipeline.process(raw_lines, {})

        assert result[0].tier1_cleaned_name == "etwas"
        assert result[0].ingredient_id is None
        assert result[0].confidence == 0.0

    def test_pipeline_respects_alias_matching(self) -> None:
        cleaner = _FakeCleaner()
        ingredients_map = {"Pouletbrust": 1}
        normalizer = IngredientNormalizer(ingredients_map)
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        raw_lines = ["300g Hähnchenbrust"]
        result = pipeline.process(raw_lines, {"Hähnchenbrust": 1})

        assert result[0].ingredient_id == 1
        assert result[0].confidence == 1.0
