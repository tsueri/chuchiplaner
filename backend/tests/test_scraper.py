import json
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

    mock.description.return_value = kwargs.get("description", None)
    mock.prep_time.return_value = kwargs.get("prep_time", None)
    mock.cook_time.return_value = kwargs.get("cook_time", None)
    mock.total_time.return_value = kwargs.get("total_time", None)
    mock.perform_time.return_value = kwargs.get("perform_time", None)
    mock.nutrients.return_value = kwargs.get("nutrients", None)
    mock.cuisine.return_value = kwargs.get("cuisine", None)
    mock.category.return_value = kwargs.get("category", None)
    mock.keywords.return_value = kwargs.get("keywords", None)
    mock.author.return_value = kwargs.get("author", None)
    mock.date_published.return_value = kwargs.get("date_published", None)
    mock.ratings.return_value = kwargs.get("ratings", None)
    mock.suitable_for_diet.return_value = kwargs.get("suitable_for_diet", None)

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


# ----- Partial extraction tests -----


def test_partial_scrape_title_when_scraper_fails() -> None:
    html = "<html><head><title>Rezept</title></head><body></body></html>"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=mock_response):
            result = RecipeScraper.scrape(
                "https://example.com/partial-title"
            )

    assert result is not None
    assert result.is_partial is True
    assert result.title == "Rezept"
    assert result.ingredients == []
    assert result.instructions == ""
    assert result.source_url == "https://example.com/partial-title"
    assert result.source_domain == "example.com"


def test_partial_scrape_extracts_og_image() -> None:
    html = (
        "<html><head>"
        '<meta property="og:image" content="https://example.com/photo.jpg">'
        "</head><body></body></html>"
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=mock_response):
            result = RecipeScraper.scrape(
                "https://example.com/og-image-recipe"
            )

    assert result is not None
    assert result.is_partial is True
    assert result.image_url == "https://example.com/photo.jpg"


def test_partial_scrape_empty_page_returns_none() -> None:
    html = "<html><head></head><body></body></html>"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=mock_response):
            result = RecipeScraper.scrape(
                "https://example.com/empty-page"
            )

    assert result is None


def test_full_scrape_returns_is_partial_false() -> None:
    mock = make_mock_scraper()
    with patch("app.services.scraper.scrape_me", return_value=mock):
        result = RecipeScraper.scrape("https://www.swissmilk.ch/rezept")
    assert result is not None
    assert result.is_partial is False


def test_partial_scrape_shares_cache() -> None:
    html = "<html><head><title>Rezept</title></head><body></body></html>"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ) as mock_scrape:
        with patch("httpx.Client.get", return_value=mock_response) as mock_http:
            result1 = RecipeScraper.scrape(
                "https://example.com/cached-partial"
            )
            result2 = RecipeScraper.scrape(
                "https://example.com/cached-partial"
            )

    assert result1 is result2
    assert mock_scrape.call_count == 1
    assert mock_http.call_count == 1


def test_partial_scrape_http_error_returns_none() -> None:
    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch(
            "httpx.Client.get",
            side_effect=Exception("connection error"),
        ):
            result = RecipeScraper.scrape(
                "https://example.com/http-error"
            )

    assert result is None


# ----- Extended schema.org fields -----


def test_scrape_fully_populated_object_exercises_every_new_field() -> None:
    mock = make_mock_scraper(
        description="A delicious Swiss dish.",
        prep_time="PT15M",
        cook_time="PT30M",
        total_time="PT45M",
        perform_time="PT10M",
        nutrients={"calories": "240 kcal", "fat": "9 g"},
        cuisine="Schweizerisch",
        category="Hauptgericht",
        keywords="schnell, einfach",
        author="Betty Bossi",
        date_published="2024-01-15",
        ratings=4.5,
        suitable_for_diet=["https://schema.org/VegetarianDiet"],
    )
    with patch("app.services.scraper.scrape_me", return_value=mock):
        result = RecipeScraper.scrape("https://www.swissmilk.ch/rezept-extended")
    assert result is not None
    assert result.title == "Test Recipe"
    assert result.description == "A delicious Swiss dish."
    assert result.prep_time_minutes == 15
    assert result.cook_time_minutes == 30
    assert result.total_time_minutes == 45
    assert result.perform_time_minutes == 10
    assert result.nutrients == {"calories": "240 kcal", "fat": "9 g"}
    assert result.cuisine == "Schweizerisch"
    assert result.category == "Hauptgericht"
    assert result.keywords == "schnell, einfach"
    assert result.author == "Betty Bossi"
    assert result.date_published is not None
    assert result.date_published.isoformat() == "2024-01-15"
    assert result.ratings == 4.5
    assert result.suitable_for_diet == ["https://schema.org/VegetarianDiet"]


def test_scrape_missing_method_returns_none_for_that_field() -> None:
    mock = make_mock_scraper(
        description="A dish.",
        # No prep_time set on mock → mock.prep_time.return_value = None
        total_time="PT30M",
        cuisine="Italienisch",
    )
    del mock.prep_time  # simulate missing method
    with patch("app.services.scraper.scrape_me", return_value=mock):
        result = RecipeScraper.scrape("https://www.swissmilk.ch/missing-method")
    assert result is not None
    assert result.title == "Test Recipe"
    assert result.description == "A dish."
    assert result.prep_time_minutes is None
    assert result.total_time_minutes == 30
    assert result.cuisine == "Italienisch"


def test_partial_scrape_populates_description_from_og_description() -> None:
    html = (
        "<html><head>"
        "<title>Rezept</title>"
        '<meta property="og:description" content="Ein schnelles Feierabend-Rezept.">'
        "</head><body></body></html>"
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=mock_response):
            result = RecipeScraper.scrape(
                "https://example.com/og-desc-recipe"
            )

    assert result is not None
    assert result.is_partial is True
    assert result.title == "Rezept"
    assert result.description == "Ein schnelles Feierabend-Rezept."


# ----- JSON-LD extraction tests -----


def _make_jsonld_html(jsonld: dict) -> str:
    ld_block = json.dumps(jsonld, ensure_ascii=False)
    return (
        "<html><head>"
        f'<script type="application/ld+json">{ld_block}</script>'
        "</head><body></body></html>"
    )


def _make_response(html: str) -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.text = html
    return mock


def test_jsonld_extracts_title_ingredients_steps() -> None:
    jsonld = {
        "@type": "Recipe",
        "name": "Spaghetti Bolognese",
        "recipeIngredient": ["200g Spaghetti", "100g Hackfleisch"],
        "recipeInstructions": [
            {"@type": "HowToStep", "text": "Kochen.", "name": "Step 1"},
        ],
    }
    html = _make_jsonld_html(jsonld)

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=_make_response(html)):
            result = RecipeScraper.scrape("https://fooby.ch/rezept")

    assert result is not None
    assert result.title == "Spaghetti Bolognese"
    assert result.ingredients == ["200g Spaghetti", "100g Hackfleisch"]
    assert result.instructions == "Kochen."
    assert result.is_partial is False


def test_jsonld_extracts_all_fields() -> None:
    jsonld = {
        "@type": "Recipe",
        "name": "Test Recipe",
        "description": "A great dish.",
        "image": "https://example.com/img.jpg",
        "recipeCategory": "Hauptgericht",
        "recipeCuisine": "Italienisch",
        "keywords": "schnell, pasta",
        "prepTime": "PT15M",
        "cookTime": "PT30M",
        "totalTime": "PT45M",
        "recipeYield": "4",
        "datePublished": "2024-01-15",
        "author": "Chef",
        "recipeIngredient": ["200g flour"],
        "recipeInstructions": "Mix and bake.",
        "nutrition": {
            "@type": "NutritionInformation",
            "calories": "240 kcal",
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.5",
        },
        "suitableForDiet": [
            "https://schema.org/VegetarianDiet",
        ],
    }
    html = _make_jsonld_html(jsonld)

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=_make_response(html)):
            result = RecipeScraper.scrape("https://example.com/rezept")

    assert result is not None
    assert result.title == "Test Recipe"
    assert result.description == "A great dish."
    assert result.image_url == "https://example.com/img.jpg"
    assert result.category == "Hauptgericht"
    assert result.cuisine == "Italienisch"
    assert result.keywords == "schnell, pasta"
    assert result.prep_time_minutes == 15
    assert result.cook_time_minutes == 30
    assert result.total_time_minutes == 45
    assert result.servings == 4
    assert result.date_published is not None
    assert result.date_published.isoformat() == "2024-01-15"
    assert result.author == "Chef"
    assert result.ingredients == ["200g flour"]
    assert result.instructions == "Mix and bake."
    assert result.nutrients == {
        "@type": "NutritionInformation",
        "calories": "240 kcal",
    }
    assert result.ratings == 4.5
    assert result.suitable_for_diet == [
        "https://schema.org/VegetarianDiet"
    ]
    assert result.is_partial is False


def test_jsonld_falls_back_to_og_meta_for_missing_fields() -> None:
    jsonld = {
        "@type": "Recipe",
        "name": "Pasta",
        "recipeIngredient": ["200g flour"],
        "recipeInstructions": "Kochen.",
    }
    html = (
        "<html><head>"
        f'<script type="application/ld+json">{json.dumps(jsonld)}</script>'
        '<meta property="og:image" content="https://example.com/og-img.jpg">'
        '<meta property="og:description" content="OG description text.">'
        "</head><body></body></html>"
    )

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=_make_response(html)):
            result = RecipeScraper.scrape("https://example.com/pasta")

    assert result is not None
    assert result.title == "Pasta"
    assert result.description == "OG description text."
    assert result.image_url == "https://example.com/og-img.jpg"
    assert result.is_partial is False


def test_jsonld_in_graph_array() -> None:
    jsonld = {
        "@graph": [
            {"@type": "WebSite", "name": "Site"},
            {
                "@type": "Recipe",
                "name": "Nested Recipe",
                "recipeIngredient": ["salt"],
                "recipeInstructions": "Mix.",
            },
        ],
    }
    html = _make_jsonld_html(jsonld)

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=_make_response(html)):
            result = RecipeScraper.scrape("https://example.com/graph")

    assert result is not None
    assert result.title == "Nested Recipe"
    assert result.ingredients == ["salt"]
    assert result.is_partial is False


def test_jsonld_no_recipe_falls_through_to_meta() -> None:
    html = (
        "<html><head>"
        "<title>Meta Title</title>"
        '<script type="application/ld+json">{"@type": "WebSite"}</script>'
        "</head><body></body></html>"
    )

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=_make_response(html)):
            result = RecipeScraper.scrape(
                "https://example.com/website-only"
            )

    assert result is not None
    assert result.is_partial is True
    assert result.title == "Meta Title"


def test_jsonld_with_empty_instructions_returns_empty_string() -> None:
    jsonld = {
        "@type": "Recipe",
        "name": "Empty Steps",
        "recipeIngredient": ["1 egg"],
    }
    html = _make_jsonld_html(jsonld)

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=_make_response(html)):
            result = RecipeScraper.scrape("https://example.com/empty")

    assert result is not None
    assert result.instructions == ""
    assert result.ingredients == ["1 egg"]
    assert result.is_partial is False


def test_jsonld_instructions_as_string_list() -> None:
    jsonld = {
        "@type": "Recipe",
        "name": "String Steps",
        "recipeIngredient": ["1 egg"],
        "recipeInstructions": [
            "Step one: crack egg.",
            "Step two: fry.",
        ],
    }
    html = _make_jsonld_html(jsonld)

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=_make_response(html)):
            result = RecipeScraper.scrape("https://example.com/strings")

    assert result is not None
    assert result.instructions == "Step one: crack egg.\nStep two: fry."


def test_jsonld_malformed_skips_to_next_block() -> None:
    html = (
        "<html><head>"
        '<script type="application/ld+json">{bad json}</script>'
        '<script type="application/ld+json">'
        '{"@type": "Recipe", "name": "OK", "recipeIngredient": [], '
        '"recipeInstructions": "Go."}'
        "</script>"
        "</head><body></body></html>"
    )

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=_make_response(html)):
            result = RecipeScraper.scrape("https://example.com/ok")

    assert result is not None
    assert result.title == "OK"
    assert result.is_partial is False


def test_jsonld_extracts_author_name_from_object() -> None:
    jsonld = {
        "@type": "Recipe",
        "name": "Author Test",
        "author": {
            "@type": "Person",
            "name": "Sebastian vom FOOBY-Team",
        },
        "recipeIngredient": ["salt"],
        "recipeInstructions": "Mix.",
    }
    html = _make_jsonld_html(jsonld)

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=_make_response(html)):
            result = RecipeScraper.scrape("https://fooby.ch/author")

    assert result is not None
    assert result.author == "Sebastian vom FOOBY-Team"
    assert result.is_partial is False


def test_jsonld_author_string_passed_through() -> None:
    jsonld = {
        "@type": "Recipe",
        "name": "String Author",
        "author": "Betty Bossi",
        "recipeIngredient": ["salt"],
        "recipeInstructions": "Mix.",
    }
    html = _make_jsonld_html(jsonld)

    with patch(
        "app.services.scraper.scrape_me", side_effect=Exception("fail")
    ):
        with patch("httpx.Client.get", return_value=_make_response(html)):
            result = RecipeScraper.scrape("https://example.com/string-author")

    assert result is not None
    assert result.author == "Betty Bossi"
