"""Tests for the training data generation script."""

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.generate_training_data import fetch_sitemap_urls


def test_import_succeeds() -> None:
    """The script module must be importable without errors."""
    importlib.import_module("scripts.generate_training_data")


def test_fetch_sitemap_urls_parses_xml() -> None:
    """fetch_sitemap_urls extracts recipe URLs from sitemap XML, filters
    non-recipe URLs, and resolves relative URLs to absolute.
    """
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/rezept/thai-curry</loc>
  </url>
  <url>
    <loc>https://example.com/rezepte/pasta-arrabiata</loc>
  </url>
  <url>
    <loc>https://example.com/recipe/ramen</loc>
  </url>
  <url>
    <loc>https://example.com/about</loc>
  </url>
  <url>
    <loc>https://example.com/contact</loc>
  </url>
  <url>
    <loc>/rezept/chili</loc>
  </url>
</urlset>"""

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = mock_xml

    with patch("scripts.generate_training_data.httpx.Client") as MockClient:
        instance = MockClient.return_value
        instance.get.return_value = mock_response
        instance.__enter__.return_value = instance

        result = fetch_sitemap_urls("https://example.com/sitemap.xml")

    assert "https://example.com/rezept/thai-curry" in result
    assert "https://example.com/rezepte/pasta-arrabiata" in result
    assert "https://example.com/recipe/ramen" in result
    assert "https://example.com/rezept/chili" in result
    assert "https://example.com/about" not in result
    assert "https://example.com/contact" not in result
    assert len(result) == 4


# ---------------------------------------------------------------------------
# build_labeling_prompt
# ---------------------------------------------------------------------------


def test_build_labeling_prompt_includes_title_and_lines() -> None:
    """Prompt includes recipe title and ingredient lines."""
    from scripts.generate_training_data import build_labeling_prompt

    prompt = build_labeling_prompt(
        "Thai Curry", ["200g Kokosmilch", "1 rote Peperoni, fein gehackt"]
    )
    assert "Thai Curry" in prompt
    assert "200g Kokosmilch" in prompt
    assert "1 rote Peperoni, fein gehackt" in prompt
    assert "json" in prompt.lower()  # asks for JSON output
    assert "dirty" in prompt.lower()
    assert "clean" in prompt.lower()


def test_build_labeling_prompt_asks_for_adjective_stripping() -> None:
    """Prompt instructs model to strip adjectives from names."""
    from scripts.generate_training_data import build_labeling_prompt

    prompt = build_labeling_prompt("Test", ["2 grüne Spargeln"])
    assert (
        "Adjektiv" in prompt
        or "adjektiv" in prompt.lower()
        or "adjective" in prompt.lower()
        or "beschreibend" in prompt.lower()
    )


# ---------------------------------------------------------------------------
# parse_deepseek_response
# ---------------------------------------------------------------------------


def test_parse_deepseek_response_valid_json() -> None:
    """Parses a valid JSON array response."""
    from scripts.generate_training_data import parse_deepseek_response

    response = (
        '[{"dirty": "2 rote Zwiebeln, gehackt", "clean": "Zwiebeln",'
        ' "reasoning": "Adjektiv und Zubereitung entfernt"}]'
    )
    result = parse_deepseek_response(response)
    assert len(result) == 1
    assert result[0]["dirty"] == "2 rote Zwiebeln, gehackt"
    assert result[0]["clean"] == "Zwiebeln"
    assert result[0]["reasoning"] == "Adjektiv und Zubereitung entfernt"


def test_parse_deepseek_response_strips_markdown_fences() -> None:
    """Strips ```json fences from response."""
    from scripts.generate_training_data import parse_deepseek_response

    response = '```json\n[{"dirty": "x", "clean": "y", "reasoning": "z"}]\n```'
    result = parse_deepseek_response(response)
    assert len(result) == 1


def test_parse_deepseek_response_raises_on_invalid_json() -> None:
    """Raises ValueError on non-JSON response."""
    from scripts.generate_training_data import parse_deepseek_response

    with pytest.raises(ValueError):
        parse_deepseek_response("not json at all")


def test_parse_deepseek_response_raises_on_missing_keys() -> None:
    """Raises ValueError if elements miss required keys."""
    from scripts.generate_training_data import parse_deepseek_response

    with pytest.raises(ValueError):
        parse_deepseek_response('[{"dirty": "x"}]')


# ---------------------------------------------------------------------------
# split_review_pairs
# ---------------------------------------------------------------------------


def test_split_review_pairs_deterministic_with_seed() -> None:
    """split_review_pairs returns consistent split with fixed seed."""
    import random

    from scripts.generate_training_data import split_review_pairs

    pairs = [
        {"dirty": f"line {i}", "clean": f"clean {i}", "reasoning": "ok"}
        for i in range(100)
    ]
    random.seed(42)
    train, review = split_review_pairs(pairs)
    assert len(train) + len(review) == 100
    # ~5% should be in review (allowing some variance)
    assert 2 <= len(review) <= 10  # 5% of 100 = 5, allow 2-10


def test_split_review_pairs_respects_fraction() -> None:
    """split_review_pairs respects custom review_fraction."""
    from scripts.generate_training_data import split_review_pairs

    pairs = [
        {"dirty": f"line {i}", "clean": f"clean {i}", "reasoning": "ok"}
        for i in range(200)
    ]
    train, review = split_review_pairs(pairs, review_fraction=0.10)
    # 10% of 200 = 20, allow 14-26
    assert 14 <= len(review) <= 26


def test_split_review_pairs_small_input() -> None:
    """split_review_pairs handles very small input gracefully."""
    from scripts.generate_training_data import split_review_pairs

    pairs = [{"dirty": "x", "clean": "y", "reasoning": "z"}]
    train, review = split_review_pairs(pairs)
    assert len(train) + len(review) == 1


def test_split_review_pairs_empty_input() -> None:
    """split_review_pairs handles empty input."""
    from scripts.generate_training_data import split_review_pairs

    train, review = split_review_pairs([])
    assert train == []
    assert review == []


# ---------------------------------------------------------------------------
# generate_training_data
# ---------------------------------------------------------------------------


def test_generate_training_data_skips_if_output_exists(tmp_path: Path) -> None:
    """generate_training_data warns and returns 0 if output file exists
    (idempotent)."""
    from scripts.generate_training_data import generate_training_data

    out = tmp_path / "pairs.jsonl"
    rev = tmp_path / "pairs_review.jsonl"
    out.write_text("existing")
    result = generate_training_data(str(out), str(rev))
    assert result == 0


def test_generate_training_data_full_pipeline(tmp_path: Path) -> None:
    """End-to-end pipeline with mocked scraping and DeepSeek."""
    import json
    from unittest.mock import MagicMock, patch

    from scripts.generate_training_data import generate_training_data

    out = tmp_path / "training.jsonl"
    rev = tmp_path / "training_review.jsonl"

    # Mock recipe scraper
    mock_recipe = MagicMock()
    mock_recipe.title = "Test Rezept"
    mock_recipe.ingredients = [
        "200g gehackte Tomaten, aus der Dose",
        "1 rote Zwiebel, fein geschnitten",
    ]
    mock_recipe.source_domain = "example.com"

    # Mock DeepSeek response
    mock_deepseek_response = MagicMock()
    mock_deepseek_choice = MagicMock()
    mock_deepseek_choice.message.content = (
        '[{"dirty": "200g gehackte Tomaten, aus der Dose",'
        ' "clean": "Tomaten",'
        ' "reasoning": "Adjektiv und Zubereitung entfernt"},'
        ' {"dirty": "1 rote Zwiebel, fein geschnitten",'
        ' "clean": "Zwiebel",'
        ' "reasoning": "Adjektiv und Zubereitung entfernt"}]'
    )
    mock_deepseek_response.choices = [mock_deepseek_choice]

    with patch(
        "scripts.generate_training_data.fetch_sitemap_urls",
        return_value=["https://example.com/rezept/test"],
    ):
        with patch(
            "scripts.generate_training_data.RecipeScraper.scrape",
            return_value=mock_recipe,
        ):
            with patch(
                "scripts.generate_training_data.OpenAI"
            ) as MockOpenAI:
                mock_client = MockOpenAI.return_value
                mock_client.chat.completions.create.return_value = (
                    mock_deepseek_response
                )

                count = generate_training_data(
                    str(out), str(rev), deepseek_api_key="test-key"
                )

    assert count == 2
    assert out.exists()
    assert rev.exists()

    # Verify JSONL content
    lines = out.read_text().strip().split("\n")
    assert len(lines) >= 1
    record = json.loads(lines[0])
    assert "dirty" in record
    assert "clean" in record
    assert "reasoning" in record
    assert "recipe_url" in record
    assert "source_domain" in record

    # Verify review file has content
    review_lines = rev.read_text().strip().split("\n")
    assert len(review_lines) >= 1
    review_record = json.loads(review_lines[0])
    assert "dirty" in review_record
    assert "clean" in review_record


def test_generate_training_data_handles_scrape_failure(tmp_path: Path) -> None:
    """Pipeline continues when RecipeScraper.scrape returns None."""
    from unittest.mock import patch

    from scripts.generate_training_data import generate_training_data

    out = tmp_path / "training.jsonl"
    rev = tmp_path / "training_review.jsonl"

    with patch(
        "scripts.generate_training_data.fetch_sitemap_urls",
        return_value=[
            "https://example.com/rezept/bad",
            "https://example.com/rezept/good",
        ],
    ):
        with patch(
            "scripts.generate_training_data.RecipeScraper.scrape",
            side_effect=[None, None],
        ):
            count = generate_training_data(
                str(out), str(rev), deepseek_api_key="test-key"
            )

    # All URLs failed to scrape, so no pairs generated
    assert count == 0
    # Output file should still not exist (nothing was written)
    assert not out.exists()
