from typing import Any
from unittest.mock import MagicMock, patch

from app.services.scraper import RecipeScraper


def make_mock_scraper(**kwargs: Any) -> MagicMock:
    mock = MagicMock()
    mock.title.return_value = kwargs.get("title", "Test Recipe")
    mock.ingredients.return_value = kwargs.get(
        "ingredients", ["200g flour", "100g sugar"]
    )
    mock.instructions.return_value = kwargs.get(
        "instructions", "Mix everything.\nBake."
    )
    mock.image.return_value = kwargs.get("image_url", None)
    mock.yields.return_value = kwargs.get("yields", "4 servings")
    return mock


def test_scrape_supported_url_returns_recipe() -> None:
    mock = make_mock_scraper(
        title="Z\u00fcrcher Geschnetzeltes",
        ingredients=["600g Kalbfleisch", "200ml Rahm"],
        instructions="Fleisch anbraten.\nRahm dazugiessen.",
        image_url="https://example.com/img.jpg",
        yields="4 Portionen",
    )
    with patch("app.services.scraper.scrape_me", return_value=mock):
        result = RecipeScraper.scrape("https://www.swissmilk.ch/rezept")
    assert result is not None
    assert result.title == "Z\u00fcrcher Geschnetzeltes"
    assert result.ingredients == ["600g Kalbfleisch", "200ml Rahm"]
    assert result.instructions == "Fleisch anbraten.\nRahm dazugiessen."
    assert result.image_url == "https://example.com/img.jpg"
    assert result.servings == 4
    assert result.source_url == "https://www.swissmilk.ch/rezept"
    assert result.source_domain == "www.swissmilk.ch"


def test_scrape_unsupported_url_returns_none() -> None:
    with patch("app.services.scraper.scrape_me", side_effect=Exception("fail")):
        result = RecipeScraper.scrape("https://example.com/recipe")
    assert result is None


def test_scrape_caches_result() -> None:
    mock = make_mock_scraper()
    with patch("app.services.scraper.scrape_me", return_value=mock) as mock_scrape:
        result1 = RecipeScraper.scrape("https://www.bettybossi.ch/rezept")
        result2 = RecipeScraper.scrape("https://www.bettybossi.ch/rezept")
    assert result1 is result2
    assert mock_scrape.call_count == 1


def test_scrape_caches_none_result() -> None:
    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ) as mock_scrape:
        result1 = RecipeScraper.scrape("https://no-recipe.example.com")
        result2 = RecipeScraper.scrape("https://no-recipe.example.com")
    assert result1 is None
    assert result2 is None
    assert mock_scrape.call_count == 1


def test_scrape_parses_servings_from_yields() -> None:
    mock = make_mock_scraper(yields="6 Personen")
    with patch("app.services.scraper.scrape_me", return_value=mock):
        result = RecipeScraper.scrape("https://www.migusto.migros.ch/rezept")
    assert result is not None
    assert result.servings == 6


def test_scrape_fallback_servings_when_yields_empty() -> None:
    mock = make_mock_scraper(yields="")
    with patch("app.services.scraper.scrape_me", return_value=mock):
        result = RecipeScraper.scrape("https://www.swissmilk.ch/rezept")
    assert result is not None
    assert result.servings == 4


def test_scrape_ingredients_failure_returns_none() -> None:
    mock = make_mock_scraper()
    mock.ingredients.side_effect = Exception("fail")
    with patch("app.services.scraper.scrape_me", return_value=mock):
        result = RecipeScraper.scrape("https://www.swissmilk.ch/rezept-ingredients-fail")
    assert result is None


def test_scrape_instructions_failure_returns_none() -> None:
    mock = make_mock_scraper()
    mock.instructions.side_effect = Exception("fail")
    with patch("app.services.scraper.scrape_me", return_value=mock):
        result = RecipeScraper.scrape("https://www.swissmilk.ch/rezept-instructions-fail")
    assert result is None
