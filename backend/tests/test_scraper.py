import json
import socket
from typing import Any
from unittest.mock import MagicMock, patch

from app.services.scraper import (
    RecipeScraper,
    SSRFBlockedError,
    resolve_and_validate_host,
    validate_url_syntax,
)


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


# ----- _fetch_url_safely tests -----


def _make_mock_http_response(
    status_code: int = 200,
    text: str = "ok",
    url: str = "https://example.com",
    headers: dict | None = None,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.headers = headers or {}
    resp.url = url
    return resp


def test_fetch_url_safely_normal_fetch() -> None:
    mock_response = _make_mock_http_response()
    with patch("socket.getaddrinfo", return_value=_make_getaddrinfo_result("93.184.216.34")):
        with patch("httpx.Client.get", return_value=mock_response) as mock_get:
            result = RecipeScraper._fetch_url_safely("https://example.com")
    assert result.status_code == 200
    assert result.text == "ok"
    mock_get.assert_called_once()


def test_fetch_url_safely_single_redirect() -> None:
    redirect_resp = _make_mock_http_response(
        status_code=301,
        headers={"Location": "https://example.com/final"},
        url="https://example.com/start",
    )
    final_resp = _make_mock_http_response(
        url="https://example.com/final",
    )

    responses: dict[str, MagicMock] = {
        "https://example.com/start": redirect_resp,
        "https://example.com/final": final_resp,
    }

    def get_side_effect(url, **kwargs):
        if url in responses:
            return responses[url]
        raise Exception(f"Unexpected URL: {url}")

    with patch("socket.getaddrinfo", return_value=_make_getaddrinfo_result("93.184.216.34")):
        with patch("httpx.Client.get", side_effect=get_side_effect) as mock_get:
            result = RecipeScraper._fetch_url_safely("https://example.com/start")
    assert result.status_code == 200
    assert mock_get.call_count == 2


def test_fetch_url_safely_redirect_to_127_0_0_1_raises() -> None:
    redirect_resp = _make_mock_http_response(
        status_code=301,
        headers={"Location": "http://127.0.0.1/"},
        url="https://example.com/start",
    )

    with patch("socket.getaddrinfo", return_value=_make_getaddrinfo_result("93.184.216.34")):
        with patch("httpx.Client.get", return_value=redirect_resp):
            try:
                RecipeScraper._fetch_url_safely("https://example.com/start")
                assert False, "should have raised"
            except SSRFBlockedError:
                pass


def test_fetch_url_safely_redirect_to_10_0_0_1_raises() -> None:
    redirect_resp = _make_mock_http_response(
        status_code=301,
        headers={"Location": "http://10.0.0.1/"},
        url="https://example.com/start",
    )

    with patch("socket.getaddrinfo", return_value=_make_getaddrinfo_result("93.184.216.34")):
        with patch("httpx.Client.get", return_value=redirect_resp):
            try:
                RecipeScraper._fetch_url_safely("https://example.com/start")
                assert False, "should have raised"
            except SSRFBlockedError:
                pass


def test_fetch_url_safely_relative_redirect() -> None:
    redirect_resp = _make_mock_http_response(
        status_code=301,
        headers={"Location": "/new-path"},
        url="https://example.com/start",
    )
    final_resp = _make_mock_http_response(
        url="https://example.com/new-path",
    )

    responses: dict[str, MagicMock] = {
        "https://example.com/start": redirect_resp,
        "https://example.com/new-path": final_resp,
    }

    def get_side_effect(url, **kwargs):
        if url in responses:
            return responses[url]
        raise Exception(f"Unexpected URL: {url}")

    with patch("socket.getaddrinfo", return_value=_make_getaddrinfo_result("93.184.216.34")):
        with patch("httpx.Client.get", side_effect=get_side_effect) as mock_get:
            result = RecipeScraper._fetch_url_safely("https://example.com/start")
    assert result.status_code == 200
    assert result.url == "https://example.com/new-path"
    assert mock_get.call_count == 2


def test_fetch_url_safely_multi_hop_redirect() -> None:
    resp1 = _make_mock_http_response(
        status_code=302,
        headers={"Location": "https://example.com/middle"},
        url="https://example.com/start",
    )
    resp2 = _make_mock_http_response(
        status_code=302,
        headers={"Location": "https://example.com/final"},
        url="https://example.com/middle",
    )
    resp3 = _make_mock_http_response(
        url="https://example.com/final",
    )

    responses: dict[str, MagicMock] = {
        "https://example.com/start": resp1,
        "https://example.com/middle": resp2,
        "https://example.com/final": resp3,
    }

    def get_side_effect(url, **kwargs):
        if url in responses:
            return responses[url]
        raise Exception(f"Unexpected URL: {url}")

    with patch("socket.getaddrinfo", return_value=_make_getaddrinfo_result("93.184.216.34")):
        with patch("httpx.Client.get", side_effect=get_side_effect) as mock_get:
            result = RecipeScraper._fetch_url_safely("https://example.com/start")
    assert result.status_code == 200
    assert mock_get.call_count == 3


def test_fetch_url_safely_max_redirects_exceeded() -> None:
    redirect_resp = _make_mock_http_response(
        status_code=301,
        headers={"Location": "https://example.com/loop"},
        url="https://example.com/start",
    )

    with patch("socket.getaddrinfo", return_value=_make_getaddrinfo_result("93.184.216.34")):
        with patch(
            "httpx.Client.get", return_value=redirect_resp
        ) as mock_get:
            try:
                RecipeScraper._fetch_url_safely("https://example.com/start")
                assert False, "should have raised"
            except SSRFBlockedError:
                pass
            assert mock_get.call_count == 6


def test_fetch_url_safely_redirect_to_private_hostname_raises() -> None:
    redirect_resp = _make_mock_http_response(
        status_code=301,
        headers={"Location": "http://internal.corp/"},
        url="https://example.com/start",
    )

    public_addr = _make_getaddrinfo_result("93.184.216.34")
    private_addr = _make_getaddrinfo_result("10.0.0.1")

    addrinfo_results = [public_addr.copy(), private_addr.copy()]

    def getaddrinfo_side_effect(hostname, *args, **kwargs):
        if hostname == "example.com":
            return addrinfo_results[0]
        if hostname == "internal.corp":
            return addrinfo_results[1]
        raise socket.gaierror("Name or service not known")

    with patch("socket.getaddrinfo", side_effect=getaddrinfo_side_effect):
        with patch("httpx.Client.get", return_value=redirect_resp):
            try:
                RecipeScraper._fetch_url_safely("https://example.com/start")
                assert False, "should have raised"
            except SSRFBlockedError:
                pass


# ----- SSRF validation primitives -----


class TestSSRFBlockedError:
    def test_inherits_from_exception(self) -> None:
        assert issubclass(SSRFBlockedError, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        try:
            raise SSRFBlockedError("blocked")
        except SSRFBlockedError as e:
            assert str(e) == "blocked"


class TestValidateUrlSyntax:
    def test_valid_https_url_returns_unchanged(self) -> None:
        result = validate_url_syntax("https://www.swissmilk.ch/recipe")
        assert result == "https://www.swissmilk.ch/recipe"

    def test_valid_http_url_returns_unchanged(self) -> None:
        result = validate_url_syntax("http://example.com/path?q=1")
        assert result == "http://example.com/path?q=1"

    def test_rejects_ftp_scheme(self) -> None:
        try:
            validate_url_syntax("ftp://example.com/file")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_missing_hostname(self) -> None:
        try:
            validate_url_syntax("https:///path")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_localhost(self) -> None:
        try:
            validate_url_syntax("http://localhost")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_localhost_with_port(self) -> None:
        try:
            validate_url_syntax("http://localhost:8000")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_loopback_ipv4_127_0_0_1(self) -> None:
        try:
            validate_url_syntax("http://127.0.0.1")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_loopback_ipv4_127_255_255_255(self) -> None:
        try:
            validate_url_syntax("http://127.255.255.255")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_private_10_0_0_0_8(self) -> None:
        try:
            validate_url_syntax("http://10.0.0.1")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_private_172_16_0_0_12(self) -> None:
        try:
            validate_url_syntax("http://172.16.0.1")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_private_172_31_255_255(self) -> None:
        try:
            validate_url_syntax("http://172.31.255.255")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_private_192_168_0_0_16(self) -> None:
        try:
            validate_url_syntax("http://192.168.1.1")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_ipv6_loopback(self) -> None:
        try:
            validate_url_syntax("http://[::1]")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_link_local_169_254(self) -> None:
        try:
            validate_url_syntax("http://169.254.1.1")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_multicast_224(self) -> None:
        try:
            validate_url_syntax("http://224.0.0.1")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_reserved_240(self) -> None:
        try:
            validate_url_syntax("http://240.0.0.1")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_unspecified_0_0_0_0(self) -> None:
        try:
            validate_url_syntax("http://0.0.0.0")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_rejects_bare_hostname_not_a_url(self) -> None:
        try:
            validate_url_syntax("not-a-url")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass

    def test_accepts_public_ipv4(self) -> None:
        result = validate_url_syntax("https://8.8.8.8/page")
        assert result == "https://8.8.8.8/page"

    def test_canonicalizes_url(self) -> None:
        result = validate_url_syntax("https://example.com/../path")
        assert result == "https://example.com/../path"

    def test_rejects_gopher_scheme(self) -> None:
        try:
            validate_url_syntax("gopher://example.com")
            assert False, "should have raised"
        except SSRFBlockedError:
            pass


def _make_getaddrinfo_result(ip: str) -> list:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


class TestResolveAndValidateHost:
    def test_public_ip_succeeds(self) -> None:
        with patch(
            "socket.getaddrinfo",
            return_value=_make_getaddrinfo_result("1.2.3.4"),
        ):
            resolve_and_validate_host("1.2.3.4")

    def test_public_hostname_succeeds(self) -> None:
        with patch(
            "socket.getaddrinfo",
            return_value=_make_getaddrinfo_result("93.184.216.34"),
        ):
            resolve_and_validate_host("example.com")

    def test_private_ip_10_0_0_1_raises(self) -> None:
        with patch(
            "socket.getaddrinfo",
            return_value=_make_getaddrinfo_result("10.0.0.1"),
        ):
            try:
                resolve_and_validate_host("10.0.0.1")
                assert False, "should have raised"
            except SSRFBlockedError:
                pass

    def test_mixed_public_private_ips_raises(self) -> None:
        with patch(
            "socket.getaddrinfo",
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", 0)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0)),
            ],
        ):
            try:
                resolve_and_validate_host("mixed.example.com")
                assert False, "should have raised"
            except SSRFBlockedError:
                pass

    def test_dns_failure_propagates(self) -> None:
        with patch(
            "socket.getaddrinfo",
            side_effect=socket.gaierror("Name or service not known"),
        ):
            try:
                resolve_and_validate_host("nonexistent.invalid")
                assert False, "should have raised"
            except socket.gaierror:
                pass

    def test_ipv6_loopback_raises(self) -> None:
        with patch(
            "socket.getaddrinfo",
            return_value=[
                (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 0, 0, 0)),
            ],
        ):
            try:
                resolve_and_validate_host("localhost6")
                assert False, "should have raised"
            except SSRFBlockedError:
                pass
