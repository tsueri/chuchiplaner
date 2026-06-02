from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.services.scraper import ScrapedRecipe


@pytest.mark.asyncio
async def test_import_recipe_supported_url(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "importuser", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    mock_recipe = ScrapedRecipe(
        title="Z\u00fcrcher Geschnetzeltes",
        ingredients=["600g Kalbfleisch", "200ml Rahm"],
        instructions="Fleisch anbraten.",
        image_url="https://img.example/recipe.jpg",
        servings=4,
        source_url="https://www.swissmilk.ch/recipe",
        source_domain="www.swissmilk.ch",
    )
    with patch(
        "app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe
    ):
        response = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.swissmilk.ch/recipe"},
            cookies=cookies,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Z\u00fcrcher Geschnetzeltes"
    assert data["ingredients"] == ["600g Kalbfleisch", "200ml Rahm"]
    assert data["servings"] == 4
    assert data["source_url"] == "https://www.swissmilk.ch/recipe"
    assert data["existing_recipe_id"] is None


@pytest.mark.asyncio
async def test_import_recipe_unsupported_url(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "importfail", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    with patch("app.api.recipes.RecipeScraper.scrape", return_value=None):
        response = await client.post(
            "/api/recipes/import",
            json={"url": "https://example.com/no-recipe"},
            cookies=cookies,
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_import_recipe_invalid_url(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "urluser", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    response = await client.post(
        "/api/recipes/import",
        json={"url": "not-a-url"},
        cookies=cookies,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_import_recipe_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/recipes/import",
        json={"url": "https://www.swissmilk.ch/recipe"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_check_url_not_yet_imported(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "checkuser", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    response = await client.get(
        "/api/recipes/check-url",
        params={"url": "https://example.com/recipe"},
        cookies=cookies,
    )
    assert response.status_code == 200
    assert response.json()["existing_recipe_id"] is None


@pytest.mark.asyncio
async def test_check_url_already_imported(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "dupcheck", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    mock_recipe = ScrapedRecipe(
        title="Test",
        ingredients=["100g flour"],
        instructions="Bake.",
        servings=2,
        source_url="https://www.swissmilk.ch/dup",
        source_domain="www.swissmilk.ch",
    )

    # First import
    with patch(
        "app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe
    ):
        import_resp = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.swissmilk.ch/dup"},
            cookies=cookies,
        )
    assert import_resp.status_code == 200

    # Now save it
    save_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Test",
            "instructions": "Bake.",
            "source_url": "https://www.swissmilk.ch/dup",
            "servings": 2,
        },
        cookies=cookies,
    )
    assert save_resp.status_code == 201

    # Check again
    response = await client.get(
        "/api/recipes/check-url",
        params={"url": "https://www.swissmilk.ch/dup"},
        cookies=cookies,
    )
    assert response.status_code == 200
    assert response.json()["existing_recipe_id"] is not None


@pytest.mark.asyncio
async def test_create_and_list_recipes(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "crecipe", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    # Create a recipe
    create_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Pasta",
            "instructions": "Cook pasta.\nAdd sauce.",
            "servings": 3,
            "source_url": "https://example.com/pasta",
            "source_domain": "example.com",
        },
        cookies=cookies,
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["title"] == "Pasta"
    assert data["servings"] == 3
    assert data["instructions"] == "Cook pasta.\nAdd sauce."
    assert data["source_url"] == "https://example.com/pasta"

    # List recipes
    list_resp = await client.get("/api/recipes", cookies=cookies)
    assert list_resp.status_code == 200
    recipes = list_resp.json()
    assert len(recipes) == 1
    assert recipes[0]["title"] == "Pasta"


@pytest.mark.asyncio
async def test_import_twice_shows_existing(
    client: AsyncClient,
) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"username": "twiceuser", "password": "secret123"},
    )
    cookies = reg_resp.cookies

    mock_recipe = ScrapedRecipe(
        title="Existing",
        ingredients=["1 egg"],
        instructions="Fry.",
        servings=1,
        source_url="https://www.swissmilk.ch/exist",
        source_domain="www.swissmilk.ch",
    )

    # Import first time
    with patch(
        "app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe
    ):
        import1 = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.swissmilk.ch/exist"},
            cookies=cookies,
        )
    assert import1.status_code == 200
    assert import1.json()["existing_recipe_id"] is None

    # Save it
    await client.post(
        "/api/recipes",
        json={
            "title": "Existing",
            "instructions": "Fry.",
            "source_url": "https://www.swissmilk.ch/exist",
            "servings": 1,
        },
        cookies=cookies,
    )

    # Import second time
    with patch(
        "app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe
    ):
        import2 = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.swissmilk.ch/exist"},
            cookies=cookies,
        )
    assert import2.status_code == 200
    assert import2.json()["existing_recipe_id"] is not None
