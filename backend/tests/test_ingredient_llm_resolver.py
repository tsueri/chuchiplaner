from unittest.mock import Mock, patch

from app.schemas.recipe import ScrapedIngredientItem
from app.services.ingredient_llm_resolver import (
    IngredientLLMResolver,
    _build_prompt,
    _parse_llm_response,
    is_critical_line,
)


class TestIsCriticalLine:
    def test_oder_pattern(self) -> None:
        assert is_critical_line("200g Mehl oder Dinkelmehl")
        assert is_critical_line("oder so was")

    def test_oder_not_triggered_by_substring(self) -> None:
        assert not is_critical_line("200g Boder")
        assert not is_critical_line("moderne Küche")

    def test_a_per_unit_pattern(self) -> None:
        assert is_critical_line("2 Stück à 100g")
        assert is_critical_line("3 Eier a 60g")

    def test_a_not_triggered_on_normal_a(self) -> None:
        assert not is_critical_line("a little bit")
        assert not is_critical_line("1 EL a la carte")

    def test_equipment_denylist(self) -> None:
        assert is_critical_line("Backpapier")
        assert is_critical_line("1 Pfanne")
        assert is_critical_line("Kochtopf mit Deckel")
        assert is_critical_line("etwas Folie")

    def test_equipment_not_triggered_by_nonequipment(self) -> None:
        assert not is_critical_line("Mehl")
        assert not is_critical_line("Zucker")

    def test_word_form_numbers(self) -> None:
        assert is_critical_line("ein wenig Salz")
        assert is_critical_line("eine Prise Zucker")
        assert is_critical_line("zwei Zweige Rosmarin")
        assert is_critical_line("drei Eier")
        assert is_critical_line("vier Äpfel")
        assert is_critical_line("fünf Kartoffeln")
        assert is_critical_line("sechs Tomaten")
        assert is_critical_line("sieben Knoblauchzehen")
        assert is_critical_line("acht Pilze")
        assert is_critical_line("neun Karotten")
        assert is_critical_line("zehn Zwiebeln")

    def test_clean_lines_not_critical(self) -> None:
        assert not is_critical_line("500g Mehl")
        assert not is_critical_line("200ml Rahm")
        assert not is_critical_line("1 EL Olivenöl")
        assert not is_critical_line("Salz und Pfeffer")


class TestNeedsTier2:
    def test_critical_pattern_routes(self) -> None:
        item = ScrapedIngredientItem(
            raw="200g Mehl oder Dinkelmehl",
            name="Mehl oder Dinkelmehl",
            quantity=200.0,
            unit="g",
            ingredient_id=1,
            confidence=1.0,
        )
        assert IngredientLLMResolver.needs_tier2(item) is True

    def test_low_confidence_routes(self) -> None:
        item = ScrapedIngredientItem(
            raw="etwas Unbekanntes",
            name="Unbekanntes",
            quantity=None,
            unit=None,
            ingredient_id=None,
            confidence=0.0,
        )
        assert IngredientLLMResolver.needs_tier2(item) is True

    def test_low_confidence_with_pattern_does_not_double_count(self) -> None:
        item = ScrapedIngredientItem(
            raw="ein wenig Mehl",
            name="Mehl",
            quantity=None,
            unit=None,
            ingredient_id=None,
            confidence=0.3,
        )
        # Should be True from either condition
        assert IngredientLLMResolver.needs_tier2(item) is True

    def test_high_confidence_clean_line_not_routed(self) -> None:
        item = ScrapedIngredientItem(
            raw="500g Mehl",
            name="Mehl",
            quantity=500.0,
            unit="g",
            ingredient_id=1,
            confidence=1.0,
        )
        assert IngredientLLMResolver.needs_tier2(item) is False

    def test_confidence_below_07_with_id_not_routed(self) -> None:
        # Confidence < 0.7 but ingredient IS resolved — shouldn't route
        item = ScrapedIngredientItem(
            raw="500g Dinkelmehl",
            name="Dinkelmehl",
            quantity=500.0,
            unit="g",
            ingredient_id=1,
            confidence=0.65,
        )
        assert IngredientLLMResolver.needs_tier2(item) is False


class TestBuildPrompt:
    def test_includes_ingredients(self) -> None:
        ingredients = {"Mehl": 1, "Zucker": 2}
        prompt = _build_prompt(["500g Mehl"], ingredients)
        assert "Mehl → 1" in prompt
        assert "Zucker → 2" in prompt

    def test_includes_raw_lines(self) -> None:
        prompt = _build_prompt(["500g Mehl", "200g Zucker"], {})
        assert "[0] 500g Mehl" in prompt
        assert "[1] 200g Zucker" in prompt

    def test_handles_empty_ingredients(self) -> None:
        prompt = _build_prompt(["500g Mehl"], {})
        assert "keine" in prompt.lower()


class TestParseLLMResponse:
    def test_parses_valid_json_array(self) -> None:
        response = json.dumps([
            {"cleaned_name": "Mehl", "confidence": 0.9},
            {"cleaned_name": "Zucker", "confidence": 0.8},
        ])
        parsed = _parse_llm_response(response, 2)
        assert len(parsed) == 2
        assert parsed[0]["cleaned_name"] == "Mehl"
        assert parsed[1]["cleaned_name"] == "Zucker"

    def test_handles_markdown_code_block(self) -> None:
        response = '```json\n[{"cleaned_name": "Mehl"}]\n```'
        parsed = _parse_llm_response(response, 1)
        assert len(parsed) == 1
        assert parsed[0]["cleaned_name"] == "Mehl"

    def test_pads_result_to_item_count(self) -> None:
        response = json.dumps([{"cleaned_name": "Mehl"}])
        parsed = _parse_llm_response(response, 3)
        assert len(parsed) == 3
        assert parsed[0]["cleaned_name"] == "Mehl"
        assert parsed[1] == {}
        assert parsed[2] == {}

    def test_truncates_result_to_item_count(self) -> None:
        response = json.dumps([
            {"cleaned_name": "A"},
            {"cleaned_name": "B"},
            {"cleaned_name": "C"},
        ])
        parsed = _parse_llm_response(response, 2)
        assert len(parsed) == 2

    def test_returns_empties_on_invalid_json(self) -> None:
        parsed = _parse_llm_response("not json", 2)
        assert parsed == [{}, {}]

    def test_wraps_single_object_into_list(self) -> None:
        parsed = _parse_llm_response('{"foo": "bar"}', 2)
        assert parsed == [{"foo": "bar"}, {}]


class TestApplyTier2Result:
    def test_applies_all_fields(self) -> None:
        item = ScrapedIngredientItem(
            raw="200g Mehl oder Dinkelmehl",
            name="Mehl oder Dinkelmehl",
            quantity=200.0,
            unit="g",
            ingredient_id=None,
            confidence=0.5,
            tier1_cleaned_name="Dinkelmehl",
        )
        result = {
            "cleaned_name": "Dinkelmehl",
            "corrected_quantity": 200,
            "corrected_unit": "g",
            "ingredient_id": 5,
            "confidence": 0.95,
            "is_equipment": False,
            "suggested_ingredient_name": None,
        }
        updated = IngredientLLMResolver.apply_tier2_result(item, result)
        assert updated.tier2_cleaned_name == "Dinkelmehl"
        assert updated.corrected_quantity == 200.0
        assert updated.corrected_unit == "g"
        assert updated.ingredient_id == 5
        assert updated.confidence == 0.95
        assert updated.is_equipment is False
        assert updated.suggested_ingredient_name is None

    def test_does_not_overwrite_with_none(self) -> None:
        item = ScrapedIngredientItem(
            raw="500g Mehl",
            name="Mehl",
            quantity=500.0,
            unit="g",
            ingredient_id=1,
            confidence=1.0,
        )
        result = {"confidence": 0.5}
        updated = IngredientLLMResolver.apply_tier2_result(item, result)
        assert updated.confidence == 0.5
        assert updated.ingredient_id == 1  # unchanged

    def test_empty_result_noop(self) -> None:
        item = ScrapedIngredientItem(
            raw="500g Mehl",
            name="Mehl",
            quantity=500.0,
            unit="g",
            ingredient_id=1,
            confidence=1.0,
        )
        updated = IngredientLLMResolver.apply_tier2_result(item, {})
        assert updated.ingredient_id == 1
        assert updated.confidence == 1.0
        assert updated.tier2_cleaned_name is None

    def test_is_equipment_string_true(self) -> None:
        item = ScrapedIngredientItem(
            raw="Backpapier",
            name="Backpapier",
            quantity=1.0,
            unit="Stück",
            ingredient_id=None,
            confidence=0.0,
        )
        updated = IngredientLLMResolver.apply_tier2_result(
            item, {"is_equipment": "true"}
        )
        assert updated.is_equipment is True

    def test_non_numeric_values_ignored(self) -> None:
        item = ScrapedIngredientItem(
            raw="500g Mehl",
            name="Mehl",
            quantity=500.0,
            unit="g",
            ingredient_id=1,
            confidence=1.0,
        )
        result = {
            "corrected_quantity": "viel",
            "ingredient_id": "abc",
            "confidence": "hoch",
        }
        updated = IngredientLLMResolver.apply_tier2_result(item, result)
        assert updated.quantity == 500.0  # original field unchanged
        assert updated.corrected_quantity is None  # tier2 field ignored
        assert updated.ingredient_id == 1  # unchanged
        assert updated.confidence == 1.0  # unchanged


class TestIngredientLLMResolver:
    def test_resolve_batch_success(self) -> None:
        resolver = IngredientLLMResolver(timeout=5.0)
        items = [
            ScrapedIngredientItem(
                raw="200g Mehl oder Dinkelmehl",
                name="Mehl oder Dinkelmehl",
                quantity=200.0,
                unit="g",
                ingredient_id=None,
                confidence=0.0,
            ),
        ]
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "response": json.dumps([
                {
                    "cleaned_name": "Dinkelmehl",
                    "corrected_quantity": 200,
                    "corrected_unit": "g",
                    "ingredient_id": 42,
                    "confidence": 0.95,
                    "is_equipment": False,
                    "suggested_ingredient_name": None,
                }
            ])
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = (
                mock_response
            )
            results = resolver.resolve_batch(items, {"Dinkelmehl": 42})

        assert len(results) == 1
        assert results[0]["cleaned_name"] == "Dinkelmehl"
        assert results[0]["ingredient_id"] == 42
        assert results[0]["confidence"] == 0.95

    def test_resolve_batch_empty_items(self) -> None:
        resolver = IngredientLLMResolver()
        results = resolver.resolve_batch([], {})
        assert results == []

    def test_resolve_batch_http_error(self) -> None:
        resolver = IngredientLLMResolver(timeout=1.0)
        items = [
            ScrapedIngredientItem(
                raw="test",
                name="test",
                quantity=None,
                unit=None,
                ingredient_id=None,
                confidence=0.0,
            ),
        ]

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = (
                Exception("connection refused")
            )
            results = resolver.resolve_batch(items, {})

        assert len(results) == 1
        assert results[0] == {}

    def test_resolve_batch_timeout(self) -> None:
        resolver = IngredientLLMResolver(timeout=0.001)
        items = [
            ScrapedIngredientItem(
                raw="test",
                name="test",
                quantity=None,
                unit=None,
                ingredient_id=None,
                confidence=0.0,
            ),
        ]

        with patch("httpx.Client") as mock_client:
            import httpx

            mock_client.return_value.__enter__.return_value.post.side_effect = (
                httpx.TimeoutException("timed out")
            )
            results = resolver.resolve_batch(items, {})

        assert len(results) == 1
        assert results[0] == {}

    def test_model_from_env(self) -> None:
        with patch.dict("os.environ", {"OLLAMA_MODEL": "mixtral:8x7b"}):
            resolver = IngredientLLMResolver()
            assert resolver._model == "mixtral:8x7b"

    def test_default_model(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            resolver = IngredientLLMResolver()
            assert resolver._model == "qwen3.5:2b"


import json  # noqa: E402


class TestPipelineRegexPostProcess:
    def test_strips_oder_alternatives(self) -> None:
        from app.services.ingredient_cleanup_pipeline import IngredientCleanupPipeline
        from app.services.normalizer import IngredientNormalizer

        class _FakeCleaner:
            def clean(self, name: str) -> str:
                return name

        cleaner = _FakeCleaner()
        normalizer = IngredientNormalizer({"Mehl": 1})
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        result = pipeline.process(["200g Mehl oder Dinkelmehl"], {})
        assert result[0].name == "Mehl"
        assert "oder" not in result[0].name

    def test_strips_a_weight_spec(self) -> None:
        from app.services.ingredient_cleanup_pipeline import IngredientCleanupPipeline
        from app.services.normalizer import IngredientNormalizer

        class _FakeCleaner:
            def clean(self, name: str) -> str:
                return name

        cleaner = _FakeCleaner()
        normalizer = IngredientNormalizer({})
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        result = pipeline.process(["1 Camembert Suisse à 300 g"], {})
        assert "300 g" not in result[0].name

    def test_strips_parentheticals(self) -> None:
        from app.services.ingredient_cleanup_pipeline import IngredientCleanupPipeline
        from app.services.normalizer import IngredientNormalizer

        class _FakeCleaner:
            def clean(self, name: str) -> str:
                return name

        cleaner = _FakeCleaner()
        normalizer = IngredientNormalizer({})
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        result = pipeline.process(["200g Rahmjoghurt (griechische Art)"], {})
        assert "(griechische Art)" not in result[0].name

    def test_detects_equipment(self) -> None:
        from app.services.ingredient_cleanup_pipeline import IngredientCleanupPipeline
        from app.services.normalizer import IngredientNormalizer

        class _FakeCleaner:
            def clean(self, name: str) -> str:
                return name

        cleaner = _FakeCleaner()
        normalizer = IngredientNormalizer({})
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        result = pipeline.process(["Backpapier"], {})
        assert result[0].is_equipment is True

    def test_strips_slash_alternatives(self) -> None:
        from app.services.ingredient_cleanup_pipeline import IngredientCleanupPipeline
        from app.services.normalizer import IngredientNormalizer

        class _FakeCleaner:
            def clean(self, name: str) -> str:
                return name

        cleaner = _FakeCleaner()
        normalizer = IngredientNormalizer({})
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        result = pipeline.process(["Runde Gratinform / Kuchenblech 30 cm"], {})
        assert "/" not in result[0].name
        assert result[0].is_equipment is True

    def test_strips_trailing_prep_notes(self) -> None:
        from app.services.ingredient_cleanup_pipeline import IngredientCleanupPipeline
        from app.services.normalizer import IngredientNormalizer

        class _FakeCleaner:
            def clean(self, name: str) -> str:
                return name

        cleaner = _FakeCleaner()
        normalizer = IngredientNormalizer({})
        pipeline = IngredientCleanupPipeline(cleaner, normalizer)

        result = pipeline.process(["3 Scheiben Brot, in Sticks geschnitten"], {})
        assert "geschnitten" not in result[0].name
