from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.scraper import ScrapedRecipe


async def _register(client: AsyncClient, username: str = "testuser") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    return {"cookies": resp.cookies, "data": resp.json()}


async def _register_and_set_role(
    client: AsyncClient,
    db_session: AsyncSession,
    username: str,
    role: str = "admin",
) -> dict:
    await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    from sqlalchemy import update

    from app.models.user import User

    await db_session.execute(
        update(User).where(User.username == username).values(role=role)
    )
    await db_session.commit()
    # Re-login to get fresh session with admin role
    login_resp = await client.post(
        "/api/auth/login",
        json={
            "username": username,
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    return {"cookies": login_resp.cookies, "data": login_resp.json()}


async def _create_recipe(
    client: AsyncClient, cookies, title="Test Recipe", **kwargs
) -> dict:
    body = {
        "title": title,
        "steps": [{"text": "Cook it."}],
        "servings": 3,
        **kwargs,
    }
    resp = await client.post("/api/recipes", json=body, cookies=cookies)
    return resp.json()


# ----- Existing tests (import, check-url, etc.) -----


@pytest.mark.asyncio
async def test_import_recipe_supported_url(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={
            "username": "importuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
    with patch("app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe):
        response = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.swissmilk.ch/recipe"},
            cookies=cookies,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Z\u00fcrcher Geschnetzeltes"
    assert len(data["ingredients"]) == 2
    assert data["ingredients"][0]["raw"] == "600g Kalbfleisch"
    assert data["ingredients"][0]["name"] == "Kalbfleisch"
    assert data["ingredients"][0]["quantity"] == 600.0
    assert data["ingredients"][0]["unit"] == "g"
    assert data["ingredients"][1]["raw"] == "200ml Rahm"
    assert data["ingredients"][1]["name"] == "Rahm"
    assert data["ingredients"][1]["quantity"] == 200.0
    assert data["ingredients"][1]["unit"] == "ml"
    assert data["is_partial"] is False
    assert data["servings"] == 4
    assert data["source_url"] == "https://www.swissmilk.ch/recipe"
    assert data["existing_recipe_id"] is None


@pytest.mark.asyncio
async def test_import_recipe_unsupported_url(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={
            "username": "importfail",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "urluser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    cookies = reg_resp.cookies

    response = await client.post(
        "/api/recipes/import",
        json={"url": "not-a-url"},
        cookies=cookies,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "URL is not allowed"


@pytest.mark.asyncio
async def test_import_recipe_localhost_rejected(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={
            "username": "localhuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    cookies = reg_resp.cookies

    response = await client.post(
        "/api/recipes/import",
        json={"url": "http://localhost"},
        cookies=cookies,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "URL is not allowed"


@pytest.mark.asyncio
async def test_import_recipe_private_ip_rejected(client: AsyncClient) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={
            "username": "privipuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
    )
    cookies = reg_resp.cookies

    response = await client.post(
        "/api/recipes/import",
        json={"url": "http://127.0.0.1"},
        cookies=cookies,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "URL is not allowed"


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
        json={
            "username": "checkuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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
        json={
            "username": "dupcheck",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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

    with patch("app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe):
        import_resp = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.swissmilk.ch/dup"},
            cookies=cookies,
        )
    assert import_resp.status_code == 200

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

    response = await client.get(
        "/api/recipes/check-url",
        params={"url": "https://www.swissmilk.ch/dup"},
        cookies=cookies,
    )
    assert response.status_code == 200
    assert response.json()["existing_recipe_id"] is not None


@pytest.mark.asyncio
async def test_create_and_list_recipes(client: AsyncClient) -> None:
    auth = await _register(client, "crecipe")
    cookies = auth["cookies"]

    create_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Pasta",
            "steps": [{"text": "Cook pasta.\nAdd sauce."}],
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
    assert data["steps"] == [
        {
            "id": data["steps"][0]["id"],
            "position": 0,
            "text": "Cook pasta.\nAdd sauce.",
            "name": None,
        }
    ]
    assert data["source_url"] == "https://example.com/pasta"

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
        json={
            "username": "twiceuser",
            "password": "secret123",
            "admin_signup_code": "test-secret",
        },
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

    with patch("app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe):
        import1 = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.swissmilk.ch/exist"},
            cookies=cookies,
        )
    assert import1.status_code == 200
    assert import1.json()["existing_recipe_id"] is None

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

    with patch("app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe):
        import2 = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.swissmilk.ch/exist"},
            cookies=cookies,
        )
    assert import2.status_code == 200
    assert import2.json()["existing_recipe_id"] is not None


# ----- Tag tests -----


@pytest.mark.asyncio
async def test_list_tags_includes_season_tags(client: AsyncClient) -> None:
    auth = await _register(client, "taglistuser")
    cookies = auth["cookies"]

    resp = await client.get("/api/tags", cookies=cookies)
    assert resp.status_code == 200
    tags = resp.json()
    season_names = [t["name"] for t in tags if t["group"] == "season"]
    assert "Frühling" in season_names
    assert "Sommer" in season_names
    assert "Herbst" in season_names
    assert "Winter" in season_names
    assert "Ganzjährig" in season_names
    for t in tags:
        if t["group"] == "season":
            assert t["household_id"] is None


@pytest.mark.asyncio
async def test_create_tag(client: AsyncClient) -> None:
    auth = await _register(client, "tagcreateuser")
    cookies = auth["cookies"]

    resp = await client.post("/api/tags", json={"name": "Grillen"}, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Grillen"
    assert data["group"] == "ingredient"

    list_resp = await client.get("/api/tags", cookies=cookies)
    tags = list_resp.json()
    names = [t["name"] for t in tags]
    assert "Grillen" in names


@pytest.mark.asyncio
async def test_create_tag_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/tags", json={"name": "Grillen"})
    assert resp.status_code == 401


# ----- Tag taxonomy extension (#48) -----


@pytest.mark.asyncio
async def test_list_tags_includes_seeded_global_groups(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "globallistuser")
    cookies = auth["cookies"]

    resp = await client.get("/api/tags", cookies=cookies)
    assert resp.status_code == 200
    tags = resp.json()

    by_group: dict[str, list[dict[str, object]]] = {}
    for t in tags:
        by_group.setdefault(t["group"], []).append(t)

    season_names = {t["name"] for t in by_group.get("season", [])}
    assert {"Frühling", "Sommer", "Herbst", "Winter", "Ganzjährig"} <= season_names

    category_names = {t["name"] for t in by_group.get("category", [])}
    expected_category = {"Vorspeise", "Hauptgericht", "Dessert", "Snack", "Beilage"}
    assert expected_category <= category_names

    cuisine_names = {t["name"] for t in by_group.get("cuisine", [])}
    assert {
        "Italienisch",
        "Asiatisch",
        "Schweizerisch",
        "Mexikanisch",
        "Indisch",
        "Französisch",
    } <= cuisine_names

    diet_names = {t["name"] for t in by_group.get("diet", [])}
    assert {
        "VegetarianDiet",
        "VeganDiet",
        "GlutenFreeDiet",
        "LowFatDiet",
        "LowLactoseDiet",
        "DiabeticDiet",
        "HalalDiet",
        "KosherDiet",
    } <= diet_names

    for group in ("season", "category", "cuisine", "diet"):
        for t in by_group.get(group, []):
            assert t["household_id"] is None, (
                f"global {group} tag {t['name']} must have household_id None"
            )


@pytest.mark.asyncio
async def test_create_tag_with_category_group_creates_global_tag(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "newcategoryuser")
    cookies = auth["cookies"]

    resp = await client.post(
        "/api/tags",
        json={"name": "Frühstück", "group": "category"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Frühstück"
    assert data["group"] == "category"
    assert data["household_id"] is None


@pytest.mark.asyncio
async def test_create_tag_with_cuisine_group_creates_global_tag(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "newcuisineuser")
    cookies = auth["cookies"]

    resp = await client.post(
        "/api/tags",
        json={"name": "Japanisch", "group": "cuisine"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Japanisch"
    assert data["group"] == "cuisine"
    assert data["household_id"] is None


@pytest.mark.asyncio
async def test_create_tag_with_diet_group_creates_global_tag(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "newdietuser")
    cookies = auth["cookies"]

    resp = await client.post(
        "/api/tags",
        json={"name": "LowSaltDiet", "group": "diet"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "LowSaltDiet"
    assert data["group"] == "diet"
    assert data["household_id"] is None


@pytest.mark.asyncio
async def test_create_tag_with_invalid_group_returns_422(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "badgroupuser")
    cookies = auth["cookies"]

    resp = await client.post(
        "/api/tags",
        json={"name": "Anything", "group": "bogus"},
        cookies=cookies,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_tag_default_group_is_ingredient(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "defaultgroupuser")
    cookies = auth["cookies"]

    resp = await client.post("/api/tags", json={"name": "MyStuff"}, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["group"] == "ingredient"
    assert data["household_id"] == auth["data"]["household_id"]


@pytest.mark.asyncio
async def test_update_recipe_category_replaces_existing_category(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "categoryreplaceuser")
    cookies = auth["cookies"]

    list_resp = await client.get("/api/tags", cookies=cookies)
    tags_by_name = {t["name"]: t for t in list_resp.json()}
    hauptgericht_id = tags_by_name["Hauptgericht"]["id"]
    vorspeise_id = tags_by_name["Vorspeise"]["id"]

    recipe = await _create_recipe(client, cookies, title="Categorized")
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"tag_ids": [hauptgericht_id]},
        cookies=cookies,
    )
    assert resp.status_code == 200
    tag_groups = {t["name"]: t["group"] for t in resp.json()["tags"]}
    assert tag_groups == {"Hauptgericht": "category"}

    resp2 = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"tag_ids": [vorspeise_id]},
        cookies=cookies,
    )
    assert resp2.status_code == 200
    tag_groups2 = {t["name"]: t["group"] for t in resp2.json()["tags"]}
    assert tag_groups2 == {"Vorspeise": "category"}
    assert "Hauptgericht" not in tag_groups2


@pytest.mark.asyncio
async def test_update_recipe_cuisine_replaces_existing_cuisine(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "cuisinereplaceuser")
    cookies = auth["cookies"]

    list_resp = await client.get("/api/tags", cookies=cookies)
    tags_by_name = {t["name"]: t for t in list_resp.json()}
    italienisch_id = tags_by_name["Italienisch"]["id"]
    asiatisch_id = tags_by_name["Asiatisch"]["id"]

    recipe = await _create_recipe(client, cookies, title="Foreign")
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"tag_ids": [italienisch_id]},
        cookies=cookies,
    )
    assert resp.status_code == 200
    assert {t["name"] for t in resp.json()["tags"]} == {"Italienisch"}

    resp2 = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"tag_ids": [asiatisch_id]},
        cookies=cookies,
    )
    assert resp2.status_code == 200
    assert {t["name"] for t in resp2.json()["tags"]} == {"Asiatisch"}


@pytest.mark.asyncio
async def test_update_recipe_diet_allows_multiple(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "dietmultiuser")
    cookies = auth["cookies"]

    list_resp = await client.get("/api/tags", cookies=cookies)
    tags_by_name = {t["name"]: t for t in list_resp.json()}
    veg_id = tags_by_name["VegetarianDiet"]["id"]
    gf_id = tags_by_name["GlutenFreeDiet"]["id"]
    ll_id = tags_by_name["LowLactoseDiet"]["id"]

    recipe = await _create_recipe(client, cookies, title="Multi-Diet")
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"tag_ids": [veg_id, gf_id, ll_id]},
        cookies=cookies,
    )
    assert resp.status_code == 200
    diet_tags = {t["name"] for t in resp.json()["tags"] if t["group"] == "diet"}
    assert diet_tags == {"VegetarianDiet", "GlutenFreeDiet", "LowLactoseDiet"}


@pytest.mark.asyncio
async def test_update_recipe_mixes_one_per_group_and_multi_value(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "mixedgroupsuser")
    cookies = auth["cookies"]

    list_resp = await client.get("/api/tags", cookies=cookies)
    tags_by_name = {t["name"]: t for t in list_resp.json()}
    haupt_id = tags_by_name["Hauptgericht"]["id"]
    dessert_id = tags_by_name["Dessert"]["id"]
    italienisch_id = tags_by_name["Italienisch"]["id"]
    asiatisch_id = tags_by_name["Asiatisch"]["id"]
    veg_id = tags_by_name["VegetarianDiet"]["id"]
    vegan_id = tags_by_name["VeganDiet"]["id"]

    recipe = await _create_recipe(client, cookies, title="Mixed")
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={
            "tag_ids": [
                haupt_id,
                italienisch_id,
                veg_id,
                vegan_id,
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200
    by_group: dict[str, list[str]] = {}
    for t in resp.json()["tags"]:
        by_group.setdefault(t["group"], []).append(t["name"])
    assert by_group["category"] == ["Hauptgericht"]
    assert by_group["cuisine"] == ["Italienisch"]
    assert sorted(by_group["diet"]) == ["VeganDiet", "VegetarianDiet"]

    resp2 = await client.put(
        f"/api/recipes/{recipe_id}",
        json={
            "tag_ids": [
                dessert_id,
                asiatisch_id,
                vegan_id,
            ]
        },
        cookies=cookies,
    )
    assert resp2.status_code == 200
    by_group2: dict[str, list[str]] = {}
    for t in resp2.json()["tags"]:
        by_group2.setdefault(t["group"], []).append(t["name"])
    assert by_group2["category"] == ["Dessert"]
    assert by_group2["cuisine"] == ["Asiatisch"]
    assert by_group2["diet"] == ["VeganDiet"]


@pytest.mark.asyncio
async def test_season_tag_still_multi_value(client: AsyncClient) -> None:
    auth = await _register(client, "seasonmultiuser")
    cookies = auth["cookies"]

    list_resp = await client.get("/api/tags", cookies=cookies)
    tags_by_name = {t["name"]: t for t in list_resp.json()}
    fr_id = tags_by_name["Frühling"]["id"]
    so_id = tags_by_name["Sommer"]["id"]

    recipe = await _create_recipe(client, cookies, title="Two Seasons")
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"tag_ids": [fr_id, so_id]},
        cookies=cookies,
    )
    assert resp.status_code == 200
    season_tags = {t["name"] for t in resp.json()["tags"] if t["group"] == "season"}
    assert season_tags == {"Frühling", "Sommer"}


# ----- Recipe detail test -----


@pytest.mark.asyncio
async def test_get_recipe_detail(client: AsyncClient) -> None:
    auth = await _register(client, "detailuser")
    cookies = auth["cookies"]

    recipe = await _create_recipe(
        client,
        cookies,
        title="Detail Recipe",
        steps=[{"text": "Step 1. Step 2."}],
        source_url="https://example.com/detail",
    )
    recipe_id = recipe["id"]

    resp = await client.get(f"/api/recipes/{recipe_id}", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Detail Recipe"
    assert data["steps"] == [
        {
            "id": data["steps"][0]["id"],
            "position": 0,
            "text": "Step 1. Step 2.",
            "name": None,
        }
    ]
    assert data["servings"] == 3
    assert data["source_url"] == "https://example.com/detail"
    assert "tags" in data
    assert "is_favorited" in data
    assert data["is_favorited"] is False


@pytest.mark.asyncio
async def test_get_recipe_detail_not_found(client: AsyncClient) -> None:
    auth = await _register(client, "detailnouser")
    cookies = auth["cookies"]

    resp = await client.get("/api/recipes/99999", cookies=cookies)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_recipe_detail_wrong_household(client: AsyncClient) -> None:
    auth1 = await _register(client, "h1user")
    cookies1 = auth1["cookies"]
    recipe = await _create_recipe(client, cookies1, title="H1 Recipe")
    recipe_id = recipe["id"]

    auth2 = await _register(client, "h2user")
    cookies2 = auth2["cookies"]

    resp = await client.get(f"/api/recipes/{recipe_id}", cookies=cookies2)
    assert resp.status_code == 404


# ----- ingredient_name on read endpoints -----


async def _create_recipe_with_ingredients(
    client: AsyncClient,
    cookies,
    title: str,
    ingredient_names: list[str],
) -> dict:
    ingredient_ids: list[int] = []
    for name in ingredient_names:
        list_resp = await client.get(
            "/api/ingredients", params={"q": name}, cookies=cookies
        )
        existing = [i for i in list_resp.json() if i["name"] == name]
        if existing:
            ingredient_ids.append(existing[0]["id"])
            continue
        ing = await client.post(
            "/api/ingredients", json={"name": name}, cookies=cookies
        )
        ingredient_ids.append(ing.json()["id"])

    body = {
        "title": title,
        "steps": [{"text": "Cook it."}],
        "servings": 4,
        "ingredients": [
            {
                "ingredient_id": ing_id,
                "quantity": 100.0,
                "unit": "g",
                "order_index": idx,
            }
            for idx, ing_id in enumerate(ingredient_ids)
        ],
    }
    resp = await client.post("/api/recipes", json=body, cookies=cookies)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_get_recipe_detail_includes_ingredient_name(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "detailnameuser")
    cookies = auth["cookies"]

    recipe = await _create_recipe_with_ingredients(
        client, cookies, title="Named", ingredient_names=["Rahm"]
    )
    recipe_id = recipe["id"]

    resp = await client.get(f"/api/recipes/{recipe_id}", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["ingredients"]) == 1
    assert data["ingredients"][0]["ingredient_name"] == "Rahm"


@pytest.mark.asyncio
async def test_list_recipes_includes_ingredient_name(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "listnameuser")
    cookies = auth["cookies"]

    await _create_recipe_with_ingredients(
        client, cookies, title="L1", ingredient_names=["Rahm", "Zwiebeln"]
    )
    await _create_recipe_with_ingredients(
        client, cookies, title="L2", ingredient_names=["Tomaten"]
    )

    resp = await client.get("/api/recipes", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    by_title = {r["title"]: r for r in data}

    assert len(by_title["L1"]["ingredients"]) == 2
    l1_names = {i["ingredient_name"] for i in by_title["L1"]["ingredients"]}
    assert l1_names == {"Rahm", "Zwiebeln"}

    assert len(by_title["L2"]["ingredients"]) == 1
    assert by_title["L2"]["ingredients"][0]["ingredient_name"] == "Tomaten"


@pytest.mark.asyncio
async def test_list_favorite_recipes_includes_ingredient_name(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "favnameuser")
    cookies = auth["cookies"]

    fav_recipe = await _create_recipe_with_ingredients(
        client, cookies, title="FavA", ingredient_names=["Rahm"]
    )
    await _create_recipe_with_ingredients(
        client, cookies, title="FavB", ingredient_names=["Zwiebeln"]
    )

    await client.post(f"/api/recipes/{fav_recipe['id']}/favorite", cookies=cookies)

    resp = await client.get("/api/recipes/favorites", cookies=cookies)
    assert resp.status_code == 200
    favs = resp.json()
    titles = [f["title"] for f in favs]
    assert "FavA" in titles
    assert "FavB" not in titles

    fav_a = next(f for f in favs if f["title"] == "FavA")
    assert len(fav_a["ingredients"]) == 1
    assert fav_a["ingredients"][0]["ingredient_name"] == "Rahm"


@pytest.mark.asyncio
async def test_list_recipes_no_n_plus_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from sqlalchemy import event

    auth = await _register(client, "nplusoneuser")
    cookies = auth["cookies"]

    ingredient_names = [f"Ing{i}" for i in range(3)]
    for i in range(5):
        await _create_recipe_with_ingredients(
            client,
            cookies,
            title=f"Recipe {i}",
            ingredient_names=ingredient_names,
        )

    queries: list[str] = []
    sync_engine = db_session.bind.sync_engine

    from sqlalchemy.engine import Connection
    from sqlalchemy.engine.interfaces import (
        CoreExecuteOptionsParameter,
        ExecutionContext,
    )

    def before_cursor_execute(
        conn: Connection,
        cursor: object,
        statement: str,
        parameters: CoreExecuteOptionsParameter,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        queries.append(statement)

    event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
    try:
        resp = await client.get("/api/recipes", params={"limit": 100}, cookies=cookies)
    finally:
        event.remove(sync_engine, "before_cursor_execute", before_cursor_execute)

    assert resp.status_code == 200
    assert len(resp.json()) == 5

    select_recipe_queries = [
        q for q in queries if "FROM recipes" in q and "SELECT" in q.upper()
    ]
    assert len(select_recipe_queries) <= 3, (
        f"Expected bounded query count for the list endpoint, got "
        f"{len(select_recipe_queries)} SELECT-from-recipes statements"
    )
    assert len(queries) <= 20, (
        f"Expected bounded query count for the list endpoint, got "
        f"{len(queries)} total statements"
    )


# ----- Recipe update test -----


@pytest.mark.asyncio
async def test_update_recipe(client: AsyncClient) -> None:
    auth = await _register(client, "updateuser")
    cookies = auth["cookies"]

    recipe = await _create_recipe(
        client, cookies, title="Old Title", steps=[{"text": "Old instr."}]
    )
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={
            "title": "New Title",
            "steps": [{"text": "New instr."}],
            "servings": 5,
        },
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "New Title"
    assert data["steps"] == [
        {
            "id": data["steps"][0]["id"],
            "position": 0,
            "text": "New instr.",
            "name": None,
        }
    ]
    assert data["servings"] == 5


@pytest.mark.asyncio
async def test_update_recipe_tags(client: AsyncClient) -> None:
    auth = await _register(client, "tagupdateuser")
    cookies = auth["cookies"]

    tag1 = await client.post("/api/tags", json={"name": "Vegetarisch"}, cookies=cookies)
    tag2 = await client.post("/api/tags", json={"name": "Schnell"}, cookies=cookies)
    tag1_id = tag1.json()["id"]
    tag2_id = tag2.json()["id"]

    recipe = await _create_recipe(client, cookies, title="Tagged")
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"tag_ids": [tag1_id, tag2_id]},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    tag_names = [t["name"] for t in data["tags"]]
    assert "Vegetarisch" in tag_names
    assert "Schnell" in tag_names

    # Remove one tag
    resp2 = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"tag_ids": [tag1_id]},
        cookies=cookies,
    )
    assert resp2.status_code == 200
    tag_names2 = [t["name"] for t in resp2.json()["tags"]]
    assert "Vegetarisch" in tag_names2
    assert "Schnell" not in tag_names2


@pytest.mark.asyncio
async def test_update_recipe_replaces_ingredients(client: AsyncClient) -> None:
    auth = await _register(client, "replacingredients")
    cookies = auth["cookies"]

    recipe = await _create_recipe_with_ingredients(
        client,
        cookies,
        title="Replace Me",
        ingredient_names=["Rahm", "Zwiebeln"],
    )
    recipe_id = recipe["id"]
    assert len(recipe["ingredients"]) == 2

    tomaten_resp = await client.post(
        "/api/ingredients", json={"name": "Tomaten"}, cookies=cookies
    )
    tomaten_id = tomaten_resp.json()["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={
            "ingredients": [
                {
                    "ingredient_id": tomaten_id,
                    "quantity": 250.0,
                    "unit": "g",
                    "order_index": 0,
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["ingredients"]) == 1
    assert data["ingredients"][0]["ingredient_id"] == tomaten_id
    assert data["ingredients"][0]["quantity"] == 250.0
    assert data["ingredients"][0]["order_index"] == 0
    assert data["ingredients"][0]["ingredient_name"] == "Tomaten"


@pytest.mark.asyncio
async def test_update_recipe_ingredients_null_preserves_existing(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "preserveingredients")
    cookies = auth["cookies"]

    recipe = await _create_recipe_with_ingredients(
        client,
        cookies,
        title="Keep Ingredients",
        ingredient_names=["Rahm", "Zwiebeln"],
    )
    recipe_id = recipe["id"]
    original_ingredient_ids = {i["ingredient_id"] for i in recipe["ingredients"]}

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Renamed", "ingredients": None},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Renamed"
    returned_ingredient_ids = {i["ingredient_id"] for i in data["ingredients"]}
    assert returned_ingredient_ids == original_ingredient_ids

    resp_omitted = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Renamed Again"},
        cookies=cookies,
    )
    assert resp_omitted.status_code == 200
    data2 = resp_omitted.json()
    returned_ingredient_ids2 = {i["ingredient_id"] for i in data2["ingredients"]}
    assert returned_ingredient_ids2 == original_ingredient_ids


@pytest.mark.asyncio
async def test_update_recipe_missing_ingredient_id_returns_400(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "missinging")
    cookies = auth["cookies"]

    recipe = await _create_recipe(client, cookies, title="Has No Ingredients")
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={
            "ingredients": [
                {
                    "ingredient_id": 99999,
                    "quantity": 1.0,
                    "unit": "g",
                    "order_index": 0,
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 400
    assert "99999" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_recipe_cross_household_returns_404(
    client: AsyncClient,
) -> None:
    auth1 = await _register(client, "updatecrossh1")
    cookies1 = auth1["cookies"]

    recipe = await _create_recipe(client, cookies1, title="H1 Only")
    recipe_id = recipe["id"]

    auth2 = await _register(client, "updatecrossh2")
    cookies2 = auth2["cookies"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Hijacked"},
        cookies=cookies2,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_recipe_member_can_edit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth_admin = await _register_and_set_role(
        client, db_session, "editadmin", role="admin"
    )
    household_id = auth_admin["data"]["household_id"]
    admin_cookies = auth_admin["cookies"]

    auth_member = await _join_household(client, db_session, "editmember", household_id)
    member_cookies = auth_member["cookies"]

    recipe = await _create_recipe(client, admin_cookies, title="Member Editable")
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Member Edited It"},
        cookies=member_cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Member Edited It"


@pytest.mark.asyncio
async def test_update_recipe_duplicate_source_url_returns_409(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "dupsourceurl")
    cookies = auth["cookies"]

    r1 = await _create_recipe(
        client,
        cookies,
        title="First",
        source_url="https://example.com/first-dup",
    )
    r2 = await _create_recipe(
        client,
        cookies,
        title="Second",
        source_url="https://example.com/second-dup",
    )

    resp = await client.put(
        f"/api/recipes/{r2['id']}",
        json={"source_url": "https://example.com/first-dup"},
        cookies=cookies,
    )
    assert resp.status_code == 409
    data = resp.json()
    assert data["existing_recipe_id"] == r1["id"]

    no_op_resp = await client.put(
        f"/api/recipes/{r1['id']}",
        json={"source_url": "https://example.com/first-dup"},
        cookies=cookies,
    )
    assert no_op_resp.status_code == 200


@pytest.mark.asyncio
async def test_update_recipe_response_has_ingredient_name(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "responsename")
    cookies = auth["cookies"]

    recipe = await _create_recipe_with_ingredients(
        client, cookies, title="Renamed", ingredient_names=["Rahm"]
    )
    recipe_id = recipe["id"]

    tomaten_resp = await client.post(
        "/api/ingredients", json={"name": "Tomaten"}, cookies=cookies
    )
    tomaten_id = tomaten_resp.json()["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={
            "ingredients": [
                {
                    "ingredient_id": tomaten_id,
                    "quantity": 100.0,
                    "unit": "g",
                    "order_index": 0,
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["ingredients"]) == 1
    assert data["ingredients"][0]["ingredient_name"] == "Tomaten"


@pytest.mark.asyncio
async def test_update_recipe_does_not_create_aliases(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "noeditaliases")
    cookies = auth["cookies"]

    ing = await client.post("/api/ingredients", json={"name": "Rahm"}, cookies=cookies)
    ingredient_id = ing.json()["id"]

    recipe = await _create_recipe(client, cookies, title="No Alias Edit")
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={
            "ingredients": [
                {
                    "ingredient_id": ingredient_id,
                    "quantity": 50.0,
                    "unit": "g",
                    "order_index": 0,
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    alias_resp = await client.get("/api/household/aliases", cookies=cookies)
    assert alias_resp.status_code == 200
    assert alias_resp.json() == []


@pytest.mark.asyncio
async def test_update_recipe_reindexes_fts_on_title_change(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "ftsreindex")
    cookies = auth["cookies"]

    recipe = await _create_recipe(
        client, cookies, title="Boring Recipe", steps=[{"text": "Plain steps."}]
    )
    recipe_id = recipe["id"]

    no_match_before = await client.get(
        "/api/recipes", params={"search": "Zucchinipfanne"}, cookies=cookies
    )
    assert no_match_before.status_code == 200
    assert no_match_before.json() == []

    rename = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Zucchinipfanne Spezial"},
        cookies=cookies,
    )
    assert rename.status_code == 200

    search_after = await client.get(
        "/api/recipes", params={"search": "Zucchinipfanne"}, cookies=cookies
    )
    assert search_after.status_code == 200
    hits = search_after.json()
    assert any(r["id"] == recipe_id for r in hits)


@pytest.mark.asyncio
async def test_update_recipe_reindexes_fts_on_step_change(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "ftsinstreindex")
    cookies = auth["cookies"]

    recipe = await _create_recipe(
        client,
        cookies,
        title="Plain",
        steps=[{"text": "Just boil water."}],
    )
    recipe_id = recipe["id"]

    no_match_before = await client.get(
        "/api/recipes", params={"search": "Kartoffelstock"}, cookies=cookies
    )
    assert no_match_before.status_code == 200
    assert no_match_before.json() == []

    rename = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"steps": [{"text": "Make a Kartoffelstock with butter and milk."}]},
        cookies=cookies,
    )
    assert rename.status_code == 200

    search_after = await client.get(
        "/api/recipes", params={"search": "Kartoffelstock"}, cookies=cookies
    )
    assert search_after.status_code == 200
    hits = search_after.json()
    assert any(r["id"] == recipe_id for r in hits)


@pytest.mark.asyncio
async def test_update_recipe_empty_ingredients_clears_set(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "emptyreplacingredients")
    cookies = auth["cookies"]

    recipe = await _create_recipe_with_ingredients(
        client,
        cookies,
        title="Will Empty",
        ingredient_names=["Rahm"],
    )
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"ingredients": []},
        cookies=cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["ingredients"] == []


# ----- Soft-delete tests -----


@pytest.mark.asyncio
async def test_admin_can_soft_delete_recipe(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth = await _register_and_set_role(client, db_session, "deladmin", role="admin")
    cookies = auth["cookies"]

    recipe = await _create_recipe(client, cookies, title="To Delete")
    recipe_id = recipe["id"]

    resp = await client.delete(f"/api/recipes/{recipe_id}", cookies=cookies)
    assert resp.status_code == 204

    list_resp = await client.get("/api/recipes", cookies=cookies)
    recipes = list_resp.json()
    titles = [r["title"] for r in recipes]
    assert "To Delete" not in titles


@pytest.mark.asyncio
async def test_member_cannot_delete_recipe(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth_admin = await _register(client, "deladmin2")
    household_id = auth_admin["data"]["household_id"]

    auth_member = await _join_household(client, db_session, "delmember2", household_id)
    member_cookies = auth_member["cookies"]

    recipe = await _create_recipe(client, member_cookies, title="No Delete")
    recipe_id = recipe["id"]

    resp = await client.delete(f"/api/recipes/{recipe_id}", cookies=member_cookies)
    assert resp.status_code == 403


# ----- Favorite tests -----


@pytest.mark.asyncio
async def test_toggle_favorite(client: AsyncClient) -> None:
    auth = await _register(client, "favuser")
    cookies = auth["cookies"]

    recipe = await _create_recipe(client, cookies, title="Fav Recipe")
    recipe_id = recipe["id"]

    resp = await client.post(f"/api/recipes/{recipe_id}/favorite", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["recipe_id"] == recipe_id

    detail = await client.get(f"/api/recipes/{recipe_id}", cookies=cookies)
    assert detail.json()["is_favorited"] is True

    resp2 = await client.post(f"/api/recipes/{recipe_id}/favorite", cookies=cookies)
    assert resp2.status_code == 200

    detail2 = await client.get(f"/api/recipes/{recipe_id}", cookies=cookies)
    assert detail2.json()["is_favorited"] is False


@pytest.mark.asyncio
async def test_list_favorite_recipes(client: AsyncClient) -> None:
    auth = await _register(client, "favlistuser")
    cookies = auth["cookies"]

    r1 = await _create_recipe(client, cookies, title="Fav 1")
    r2 = await _create_recipe(client, cookies, title="Fav 2")
    await _create_recipe(client, cookies, title="Not Fav")

    await client.post(f"/api/recipes/{r1['id']}/favorite", cookies=cookies)
    await client.post(f"/api/recipes/{r2['id']}/favorite", cookies=cookies)

    resp = await client.get("/api/recipes/favorites", cookies=cookies)
    assert resp.status_code == 200
    favs = resp.json()
    fav_titles = [f["title"] for f in favs]
    assert "Fav 1" in fav_titles
    assert "Fav 2" in fav_titles
    assert "Not Fav" not in fav_titles


@pytest.mark.asyncio
async def test_filter_recipes_by_favorites(client: AsyncClient) -> None:
    auth = await _register(client, "favfilteruser")
    cookies = auth["cookies"]

    r = await _create_recipe(client, cookies, title="Only Fav")
    await _create_recipe(client, cookies, title="Other")
    await client.post(f"/api/recipes/{r['id']}/favorite", cookies=cookies)

    resp = await client.get(
        "/api/recipes", params={"favorites_only": "true"}, cookies=cookies
    )
    assert resp.status_code == 200
    results = resp.json()
    titles = [item["title"] for item in results]
    assert "Only Fav" in titles
    assert "Other" not in titles


# ----- Search tests -----


@pytest.mark.asyncio
async def test_search_recipes_by_title(client: AsyncClient) -> None:
    auth = await _register(client, "searchuser")
    cookies = auth["cookies"]

    await _create_recipe(client, cookies, title="Spaghetti Bolognese")
    await _create_recipe(client, cookies, title="Chicken Curry")

    resp = await client.get(
        "/api/recipes", params={"search": "Spaghetti"}, cookies=cookies
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Spaghetti Bolognese"


@pytest.mark.asyncio
async def test_search_recipes_by_steps(client: AsyncClient) -> None:
    auth = await _register(client, "searchinstuser")
    cookies = auth["cookies"]

    await _create_recipe(
        client,
        cookies,
        title="Risotto",
        steps=[{"text": "Use Arborio rice and Parmesan."}],
    )
    await _create_recipe(
        client,
        cookies,
        title="Pasta",
        steps=[{"text": "Boil water and cook."}],
    )

    resp = await client.get(
        "/api/recipes", params={"search": "Arborio"}, cookies=cookies
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Risotto"


@pytest.mark.asyncio
async def test_search_recipes_by_ingredient_only(client: AsyncClient) -> None:
    auth = await _register(client, "searchingredientonly")
    cookies = auth["cookies"]

    await _create_recipe_with_ingredients(
        client, cookies, title="Pasta", ingredient_names=["Tomate"]
    )
    await _create_recipe(client, cookies, title="Boring Steak")

    resp = await client.get(
        "/api/recipes", params={"search": "Tomate"}, cookies=cookies
    )
    assert resp.status_code == 200
    data = resp.json()
    titles = [r["title"] for r in data]
    assert "Pasta" in titles
    assert "Boring Steak" not in titles


@pytest.mark.asyncio
async def test_search_reweighting_ingredients_above_steps_above_title(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "searchreweight")
    cookies = auth["cookies"]

    r_ingredient = await _create_recipe_with_ingredients(
        client,
        cookies,
        title="Pasta",
        ingredient_names=["Tomatenpaste"],
    )
    r_step = await _create_recipe(
        client,
        cookies,
        title="Pizza",
        steps=[{"text": "Use Tomatenpaste sauce."}],
    )
    r_title = await _create_recipe(
        client,
        cookies,
        title="Tomatenpaste Spezial",
        steps=[{"text": "Cook it."}],
    )

    resp = await client.get(
        "/api/recipes", params={"search": "Tomatenpaste"}, cookies=cookies
    )
    assert resp.status_code == 200
    data = resp.json()
    ids = [r["id"] for r in data]

    assert r_ingredient["id"] in ids
    assert r_step["id"] in ids
    assert r_title["id"] in ids

    pos_ing = ids.index(r_ingredient["id"])
    pos_step = ids.index(r_step["id"])
    pos_title = ids.index(r_title["id"])
    assert pos_ing < pos_step, (
        f"ingredient hit must rank above steps hit; got order {ids}"
    )
    assert pos_step < pos_title, f"steps hit must rank above title hit; got order {ids}"


@pytest.mark.asyncio
async def test_search_like_fallback_when_fts_returns_nothing(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "searchlikefb")
    cookies = auth["cookies"]

    await _create_recipe(client, cookies, title="Plain Spaghetti")

    resp = await client.get("/api/recipes", params={"search": "Spagh"}, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    titles = [r["title"] for r in data]
    assert "Plain Spaghetti" in titles


@pytest.mark.asyncio
async def test_search_title_like_substring_union_with_fts(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "searchlikeunion")
    cookies = auth["cookies"]

    r_substring = await _create_recipe(
        client, cookies, title="Tomatencremesuppe", steps=[{"text": "Cook."}]
    )
    r_fts = await _create_recipe_with_ingredients(
        client,
        cookies,
        title="Pasta Asciutta",
        ingredient_names=["Tomate"],
    )

    resp = await client.get(
        "/api/recipes", params={"search": "Tomate"}, cookies=cookies
    )
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert r_substring["id"] in ids
    assert r_fts["id"] in ids
    assert ids.index(r_fts["id"]) < ids.index(r_substring["id"])


# ----- Tag filter tests -----


@pytest.mark.asyncio
async def test_filter_recipes_by_tag(client: AsyncClient) -> None:
    auth = await _register(client, "tagfilteruser")
    cookies = auth["cookies"]

    tag = await client.post("/api/tags", json={"name": "Vegan"}, cookies=cookies)
    tag_id = tag.json()["id"]

    r1 = await _create_recipe(client, cookies, title="Salad")
    await _create_recipe(client, cookies, title="Steak")

    await client.put(
        f"/api/recipes/{r1['id']}",
        json={"tag_ids": [tag_id]},
        cookies=cookies,
    )

    resp = await client.get("/api/recipes", params={"tag_id": tag_id}, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    titles = [r["title"] for r in data]
    assert "Salad" in titles
    assert "Steak" not in titles


# ----- Note tests -----


@pytest.mark.asyncio
async def test_create_and_list_notes(client: AsyncClient) -> None:
    auth = await _register(client, "noteuser")
    cookies = auth["cookies"]

    recipe = await _create_recipe(client, cookies, title="Note Recipe")
    recipe_id = recipe["id"]

    resp = await client.post(
        f"/api/recipes/{recipe_id}/notes",
        json={"text": "Use less salt next time.", "visibility": "private"},
        cookies=cookies,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["text"] == "Use less salt next time."
    assert data["visibility"] == "private"
    assert data["username"] == "noteuser"

    list_resp = await client.get(f"/api/recipes/{recipe_id}/notes", cookies=cookies)
    assert list_resp.status_code == 200
    notes = list_resp.json()
    assert len(notes) == 1


async def _join_household(
    client: AsyncClient,
    db_session: AsyncSession,
    username: str,
    household_id: int,
) -> dict:
    from sqlalchemy import select

    from app.models.household import Household

    result = await db_session.execute(
        select(Household).where(Household.id == household_id)
    )
    household = result.scalar_one_or_none()
    invite_code = household.invite_code if household else None

    resp = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "secret123",
            "invite_code": invite_code,
        },
    )
    return {"cookies": resp.cookies, "data": resp.json()}


@pytest.mark.asyncio
async def test_private_notes_not_visible_to_others(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth1 = await _register(client, "noteuser1")
    cookies1 = auth1["cookies"]
    household_id = auth1["data"]["household_id"]

    recipe = await _create_recipe(client, cookies1, title="Shared Recipe")
    recipe_id = recipe["id"]

    await client.post(
        f"/api/recipes/{recipe_id}/notes",
        json={"text": "My secret note.", "visibility": "private"},
        cookies=cookies1,
    )

    auth2 = await _join_household(client, db_session, "noteuser2", household_id)
    cookies2 = auth2["cookies"]

    list_resp = await client.get(f"/api/recipes/{recipe_id}/notes", cookies=cookies2)
    assert list_resp.status_code == 200
    notes = list_resp.json()
    assert len(notes) == 0


@pytest.mark.asyncio
async def test_household_note_visible_to_members(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth1 = await _register(client, "hnoteuser1")
    cookies1 = auth1["cookies"]
    household_id = auth1["data"]["household_id"]

    recipe = await _create_recipe(client, cookies1, title="House Recipe")
    recipe_id = recipe["id"]

    await client.post(
        f"/api/recipes/{recipe_id}/notes",
        json={"text": "Household tip!", "visibility": "household"},
        cookies=cookies1,
    )

    auth2 = await _join_household(client, db_session, "hnoteuser2", household_id)
    cookies2 = auth2["cookies"]

    list_resp = await client.get(f"/api/recipes/{recipe_id}/notes", cookies=cookies2)
    assert list_resp.status_code == 200
    notes = list_resp.json()
    assert len(notes) == 1
    assert notes[0]["text"] == "Household tip!"
    assert notes[0]["username"] == "hnoteuser1"


@pytest.mark.asyncio
async def test_update_note(client: AsyncClient) -> None:
    auth = await _register(client, "noteupdateuser")
    cookies = auth["cookies"]

    recipe = await _create_recipe(client, cookies, title="Update Note")
    recipe_id = recipe["id"]

    note_resp = await client.post(
        f"/api/recipes/{recipe_id}/notes",
        json={"text": "Original text.", "visibility": "private"},
        cookies=cookies,
    )
    note_id = note_resp.json()["id"]

    update_resp = await client.put(
        f"/api/recipes/{recipe_id}/notes/{note_id}",
        json={"text": "Updated text.", "visibility": "household"},
        cookies=cookies,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["text"] == "Updated text."
    assert data["visibility"] == "household"


@pytest.mark.asyncio
async def test_delete_note(client: AsyncClient) -> None:
    auth = await _register(client, "notedeluser")
    cookies = auth["cookies"]

    recipe = await _create_recipe(client, cookies, title="Del Note")
    recipe_id = recipe["id"]

    note_resp = await client.post(
        f"/api/recipes/{recipe_id}/notes",
        json={"text": "To be deleted.", "visibility": "private"},
        cookies=cookies,
    )
    note_id = note_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/recipes/{recipe_id}/notes/{note_id}", cookies=cookies
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(f"/api/recipes/{recipe_id}/notes", cookies=cookies)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_cannot_update_others_note(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth1 = await _register(client, "noteo1")
    cookies1 = auth1["cookies"]
    household_id = auth1["data"]["household_id"]

    recipe = await _create_recipe(client, cookies1, title="No Touch")
    recipe_id = recipe["id"]

    note_resp = await client.post(
        f"/api/recipes/{recipe_id}/notes",
        json={"text": "Mine.", "visibility": "household"},
        cookies=cookies1,
    )
    note_id = note_resp.json()["id"]

    auth2 = await _join_household(client, db_session, "noteo2", household_id)
    cookies2 = auth2["cookies"]

    update_resp = await client.put(
        f"/api/recipes/{recipe_id}/notes/{note_id}",
        json={"text": "Hijack!", "visibility": "private"},
        cookies=cookies2,
    )
    assert update_resp.status_code == 404


# ----- Pagination test -----


@pytest.mark.asyncio
async def test_recipe_list_pagination(client: AsyncClient) -> None:
    auth = await _register(client, "pageuser")
    cookies = auth["cookies"]

    for i in range(5):
        await _create_recipe(client, cookies, title=f"Recipe {i}")

    resp = await client.get(
        "/api/recipes",
        params={"limit": 2, "offset": 0},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


# ----- Learned aliases -----


@pytest.mark.asyncio
async def test_create_recipe_alias_conflict_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth = await _register(client, "aliasconflict")
    cookies = auth["cookies"]

    ing = await client.post("/api/ingredients", json={"name": "Rahm"}, cookies=cookies)
    ingredient_id = ing.json()["id"]

    await client.post(
        "/api/household/aliases",
        json={"ingredient_id": ingredient_id, "alias_name": "Sahne"},
        cookies=cookies,
    )
    await db_session.commit()

    resp = await client.post(
        "/api/recipes",
        json={
            "title": "Rahmsosse",
            "instructions": "Kochen.",
            "servings": 2,
            "learned_aliases": [
                {"alias_name": "Sahne", "ingredient_id": ingredient_id},
            ],
        },
        cookies=cookies,
    )
    assert resp.status_code == 201  # duplicate alias is silently skipped
    assert resp.json()["title"] == "Rahmsosse"

    # Recipe was created successfully despite pre-existing alias.
    list_resp = await client.get("/api/recipes", cookies=cookies)
    recipes = list_resp.json()
    titles = [r["title"] for r in recipes]
    assert "Rahmsosse" in titles


@pytest.mark.asyncio
async def test_create_recipe_empty_learned_aliases_noop(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "aliasempty")
    cookies = auth["cookies"]

    resp = await client.post(
        "/api/recipes",
        json={
            "title": "Pasta",
            "instructions": "Cook.",
            "servings": 2,
            "learned_aliases": [],
        },
        cookies=cookies,
    )
    assert resp.status_code == 201

    alias_resp = await client.get("/api/household/aliases", cookies=cookies)
    assert alias_resp.status_code == 200
    assert len(alias_resp.json()) == 0


@pytest.mark.asyncio
async def test_create_recipe_learned_aliases_missing_noop(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "aliasmissing")
    cookies = auth["cookies"]

    resp = await client.post(
        "/api/recipes",
        json={
            "title": "Pasta",
            "instructions": "Cook.",
            "servings": 2,
        },
        cookies=cookies,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_recipe_invalid_ingredient_alias_400(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "aliasinvalid")
    cookies = auth["cookies"]

    resp = await client.post(
        "/api/recipes",
        json={
            "title": "Pasta",
            "instructions": "Cook.",
            "servings": 2,
            "learned_aliases": [
                {"alias_name": "Foo", "ingredient_id": 99999},
            ],
        },
        cookies=cookies,
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()
    assert "99999" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_recipe_persists_learned_aliases(client: AsyncClient) -> None:
    auth = await _register(client, "aliaslearn")
    cookies = auth["cookies"]

    ing = await client.post(
        "/api/ingredients", json={"name": "Tomaten"}, cookies=cookies
    )
    ingredient_id = ing.json()["id"]

    resp = await client.post(
        "/api/recipes",
        json={
            "title": "Pasta",
            "instructions": "Cook.",
            "servings": 2,
            "learned_aliases": [
                {"alias_name": "Tomäntli", "ingredient_id": ingredient_id},
            ],
        },
        cookies=cookies,
    )
    assert resp.status_code == 201

    alias_resp = await client.get("/api/household/aliases", cookies=cookies)
    assert alias_resp.status_code == 200
    aliases = alias_resp.json()
    assert len(aliases) == 1
    assert aliases[0]["alias_name"] == "Tomäntli"
    assert aliases[0]["ingredient_id"] == ingredient_id


# ----- Source URL duplicate checks -----


@pytest.mark.asyncio
async def test_create_recipe_409_same_household_duplicate_source_url(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "dup409user")
    cookies = auth["cookies"]

    await client.post(
        "/api/recipes",
        json={
            "title": "Original",
            "instructions": "Steps.",
            "source_url": "https://example.com/duplicate",
            "servings": 2,
        },
        cookies=cookies,
    )

    resp = await client.post(
        "/api/recipes",
        json={
            "title": "Duplicate",
            "instructions": "Steps.",
            "source_url": "https://example.com/duplicate",
            "servings": 2,
        },
        cookies=cookies,
    )
    assert resp.status_code == 409
    data = resp.json()
    assert "detail" in data
    assert data["existing_recipe_id"] is not None


@pytest.mark.asyncio
async def test_create_recipe_no_409_cross_household_source_url(
    client: AsyncClient,
) -> None:
    auth1 = await _register(client, "crossh1")
    cookies1 = auth1["cookies"]

    await client.post(
        "/api/recipes",
        json={
            "title": "H1 Recipe",
            "instructions": "Steps.",
            "source_url": "https://example.com/crosshouse",
            "servings": 2,
        },
        cookies=cookies1,
    )

    auth2 = await _register(client, "crossh2")
    cookies2 = auth2["cookies"]

    resp = await client.post(
        "/api/recipes",
        json={
            "title": "H2 Recipe",
            "instructions": "Steps.",
            "source_url": "https://example.com/crosshouse",
            "servings": 2,
        },
        cookies=cookies2,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_recipe_201_after_soft_delete_source_url(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth = await _register_and_set_role(client, db_session, "softdeldup", role="admin")
    cookies = auth["cookies"]

    recipe = await _create_recipe(
        client,
        cookies,
        title="To Soft Delete",
        source_url="https://example.com/softdel",
    )
    recipe_id = recipe["id"]

    del_resp = await client.delete(f"/api/recipes/{recipe_id}", cookies=cookies)
    assert del_resp.status_code == 204

    resp = await client.post(
        "/api/recipes",
        json={
            "title": "Fresh",
            "instructions": "Steps.",
            "source_url": "https://example.com/softdel",
            "servings": 2,
        },
        cookies=cookies,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_recipe_no_false_409_null_source_url(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "nullurluser")
    cookies = auth["cookies"]

    r1 = await client.post(
        "/api/recipes",
        json={
            "title": "First",
            "instructions": "Steps.",
            "servings": 2,
        },
        cookies=cookies,
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/recipes",
        json={
            "title": "Second",
            "instructions": "Steps.",
            "servings": 2,
        },
        cookies=cookies,
    )
    assert r2.status_code == 201


@pytest.mark.asyncio
async def test_reimport_colliding_url_upserts_existing_row(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "reimportuser")
    cookies = auth["cookies"]

    ing = await client.post("/api/ingredients", json={"name": "Rahm"}, cookies=cookies)
    ingredient_id = ing.json()["id"]

    original = await _create_recipe(
        client,
        cookies,
        title="Original",
        source_url="https://example.com/upsert-target",
        steps=[{"text": "Original step."}],
    )
    original_id = original["id"]

    resp = await client.post(
        "/api/recipes",
        json={
            "reimport": True,
            "title": "Updated Title",
            "description": "Updated description",
            "steps": [
                {"position": 0, "text": "New step 1", "name": None},
                {"position": 1, "text": "New step 2", "name": None},
            ],
            "servings": 6,
            "prep_time_minutes": 20,
            "total_time_minutes": 45,
            "source_url": "https://example.com/upsert-target",
            "source_domain": "example.com",
            "image_url": "https://img.example/new.jpg",
            "ingredients": [
                {
                    "ingredient_id": ingredient_id,
                    "quantity": 250.0,
                    "unit": "g",
                    "order_index": 0,
                }
            ],
        },
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == original_id
    assert data["title"] == "Updated Title"
    assert data["description"] == "Updated description"
    assert data["servings"] == 6
    assert data["prep_time_minutes"] == 20
    assert data["total_time_minutes"] == 45
    assert data["image_url"] == "https://img.example/new.jpg"
    assert data["source_url"] == "https://example.com/upsert-target"
    assert data["source_domain"] == "example.com"
    assert len(data["ingredients"]) == 1
    assert data["ingredients"][0]["ingredient_id"] == ingredient_id
    assert data["ingredients"][0]["quantity"] == 250.0
    assert data["ingredients"][0]["unit"] == "g"
    assert len(data["steps"]) == 2
    assert data["steps"][0]["text"] == "New step 1"
    assert data["steps"][1]["text"] == "New step 2"

    list_resp = await client.get("/api/recipes", cookies=cookies)
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert len(list_data) == 1
    assert list_data[0]["id"] == original_id
    assert list_data[0]["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_reimport_new_url_creates_recipe_201(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "reimportnew")
    cookies = auth["cookies"]

    resp = await client.post(
        "/api/recipes",
        json={
            "reimport": True,
            "title": "Fresh",
            "steps": [{"text": "New."}],
            "source_url": "https://example.com/fresh-import",
            "servings": 2,
        },
        cookies=cookies,
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Fresh"
    assert resp.json()["source_url"] == "https://example.com/fresh-import"


@pytest.mark.asyncio
async def test_reimport_applies_tag_ids_with_one_per_group_rule(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "reimporttags")
    cookies = auth["cookies"]

    tags_resp = await client.get("/api/tags", cookies=cookies)
    tags_by_name = {t["name"]: t for t in tags_resp.json()}
    hauptgericht_id = tags_by_name["Hauptgericht"]["id"]
    italienisch_id = tags_by_name["Italienisch"]["id"]
    asiatisch_id = tags_by_name["Asiatisch"]["id"]
    vegetarian_id = tags_by_name["VegetarianDiet"]["id"]
    vegan_id = tags_by_name["VeganDiet"]["id"]

    original = await _create_recipe(
        client,
        cookies,
        title="Tag Upsert Target",
        source_url="https://example.com/tag-upsert",
    )
    original_id = original["id"]

    put_resp = await client.put(
        f"/api/recipes/{original_id}",
        json={"tag_ids": [hauptgericht_id, italienisch_id, vegetarian_id]},
        cookies=cookies,
    )
    assert put_resp.status_code == 200

    resp = await client.post(
        "/api/recipes",
        json={
            "reimport": True,
            "title": "Tag Upsert Target",
            "source_url": "https://example.com/tag-upsert",
            "tag_ids": [hauptgericht_id, asiatisch_id, vegan_id],
        },
        cookies=cookies,
    )
    assert resp.status_code == 200
    tag_ids = {t["id"] for t in resp.json()["tags"]}
    assert hauptgericht_id in tag_ids
    assert asiatisch_id in tag_ids
    assert italienisch_id not in tag_ids
    assert vegan_id in tag_ids
    assert vegetarian_id not in tag_ids


@pytest.mark.asyncio
async def test_create_recipe_409_preserved_when_reimport_false(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "manual409user")
    cookies = auth["cookies"]

    await client.post(
        "/api/recipes",
        json={
            "title": "Original",
            "instructions": "Steps.",
            "source_url": "https://example.com/manual-409",
            "servings": 2,
        },
        cookies=cookies,
    )

    resp = await client.post(
        "/api/recipes",
        json={
            "reimport": False,
            "title": "Duplicate",
            "instructions": "Steps.",
            "source_url": "https://example.com/manual-409",
            "servings": 2,
        },
        cookies=cookies,
    )
    assert resp.status_code == 409
    data = resp.json()
    assert "detail" in data
    assert data["existing_recipe_id"] is not None


@pytest.mark.asyncio
async def test_import_existing_lookup_filters_by_household(
    client: AsyncClient,
) -> None:
    mock_recipe = ScrapedRecipe(
        title="Shared URL",
        ingredients=["1 egg"],
        instructions="Fry.",
        servings=1,
        source_url="https://www.swissmilk.ch/crosshouse-import",
        source_domain="www.swissmilk.ch",
    )

    auth1 = await _register(client, "imph1")
    cookies1 = auth1["cookies"]

    with patch("app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe):
        import1 = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.swissmilk.ch/crosshouse-import"},
            cookies=cookies1,
        )
    assert import1.status_code == 200
    assert import1.json()["existing_recipe_id"] is None

    await client.post(
        "/api/recipes",
        json={
            "title": "H1 Saved",
            "instructions": "Fry.",
            "source_url": "https://www.swissmilk.ch/crosshouse-import",
            "servings": 1,
        },
        cookies=cookies1,
    )

    auth2 = await _register(client, "imph2")
    cookies2 = auth2["cookies"]

    with patch("app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe):
        import2 = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.swissmilk.ch/crosshouse-import"},
            cookies=cookies2,
        )
    assert import2.status_code == 200
    assert import2.json()["existing_recipe_id"] is None


# ----- RecipeStep CRUD / cascade-delete -----


@pytest.mark.asyncio
async def test_get_recipe_detail_returns_steps(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "stepdetail")
    cookies = auth["cookies"]

    create_resp = await client.post(
        "/api/recipes",
        json={
            "title": "Mit Schritten",
            "steps": [
                {"position": 0, "text": "Erster Schritt", "name": "Vorbereiten"},
                {"position": 1, "text": "Zweiter Schritt", "name": None},
            ],
        },
        cookies=cookies,
    )
    assert create_resp.status_code == 201
    recipe_id = create_resp.json()["id"]

    detail = await client.get(f"/api/recipes/{recipe_id}", cookies=cookies)
    assert detail.status_code == 200
    data = detail.json()
    assert len(data["steps"]) == 2
    assert data["steps"][0]["position"] == 0
    assert data["steps"][0]["text"] == "Erster Schritt"
    assert data["steps"][0]["name"] == "Vorbereiten"
    assert data["steps"][1]["position"] == 1
    assert data["steps"][1]["text"] == "Zweiter Schritt"
    assert data["steps"][1]["name"] is None


@pytest.mark.asyncio
async def test_update_recipe_replaces_steps(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "stepreplace")
    cookies = auth["cookies"]

    create = await client.post(
        "/api/recipes",
        json={
            "title": "Replace Steps",
            "steps": [
                {"position": 0, "text": "Alt 1", "name": None},
                {"position": 1, "text": "Alt 2", "name": None},
            ],
        },
        cookies=cookies,
    )
    assert create.status_code == 201
    recipe_id = create.json()["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={
            "steps": [
                {"position": 0, "text": "Neu 1", "name": "Phase"},
                {"position": 1, "text": "Neu 2", "name": None},
                {"position": 2, "text": "Neu 3", "name": None},
            ],
        },
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["steps"]) == 3
    positions = sorted(s["position"] for s in data["steps"])
    assert positions == [0, 1, 2]
    assert data["steps"][0]["text"] == "Neu 1"
    assert data["steps"][0]["name"] == "Phase"


@pytest.mark.asyncio
async def test_update_recipe_null_steps_preserves_existing(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "steppreserve")
    cookies = auth["cookies"]

    create = await client.post(
        "/api/recipes",
        json={
            "title": "Keep Steps",
            "steps": [
                {"position": 0, "text": "Bleibt 1", "name": None},
                {"position": 1, "text": "Bleibt 2", "name": None},
            ],
        },
        cookies=cookies,
    )
    assert create.status_code == 201
    recipe_id = create.json()["id"]
    original_step_texts = sorted(s["text"] for s in create.json()["steps"])

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Renamed", "steps": None},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Renamed"
    assert sorted(s["text"] for s in data["steps"]) == original_step_texts

    resp_omitted = await client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Renamed Again"},
        cookies=cookies,
    )
    assert resp_omitted.status_code == 200
    data2 = resp_omitted.json()
    assert sorted(s["text"] for s in data2["steps"]) == original_step_texts


@pytest.mark.asyncio
async def test_recipe_step_cascade_delete(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth = await _register_and_set_role(client, db_session, "stepcascade", role="admin")
    cookies = auth["cookies"]

    from sqlalchemy import select

    from app.models.recipe import Recipe, RecipeStep

    create = await client.post(
        "/api/recipes",
        json={
            "title": "Will Delete",
            "steps": [
                {"position": 0, "text": "A", "name": None},
                {"position": 1, "text": "B", "name": None},
            ],
        },
        cookies=cookies,
    )
    assert create.status_code == 201
    recipe_id = create.json()["id"]

    pre_count = (
        (
            await db_session.execute(
                select(RecipeStep).where(RecipeStep.recipe_id == recipe_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(pre_count) == 2

    recipe_obj = (
        await db_session.execute(select(Recipe).where(Recipe.id == recipe_id))
    ).scalar_one()
    await db_session.delete(recipe_obj)
    await db_session.commit()

    post_count = (
        (
            await db_session.execute(
                select(RecipeStep).where(RecipeStep.recipe_id == recipe_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(post_count) == 0


@pytest.mark.asyncio
async def test_recipe_step_unique_position(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth = await _register(client, "stepunique")
    cookies = auth["cookies"]

    create = await client.post(
        "/api/recipes",
        json={
            "title": "Uniq",
            "steps": [
                {"position": 0, "text": "A", "name": None},
            ],
        },
        cookies=cookies,
    )
    assert create.status_code == 201
    recipe_id = create.json()["id"]

    from sqlalchemy import text

    with pytest.raises(Exception):
        await db_session.execute(
            text(
                "INSERT INTO recipe_steps (recipe_id, position, text, name) "
                f"VALUES ({recipe_id}, 0, 'B', NULL)"
            )
        )


# ----- New field round-trips -----


@pytest.mark.asyncio
async def test_create_recipe_with_new_fields_round_trips(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "newfields")
    cookies = auth["cookies"]

    create = await client.post(
        "/api/recipes",
        json={
            "title": "Mit allen Feldern",
            "description": "Kurze Zusammenfassung",
            "prep_time_minutes": 15,
            "cook_time_minutes": 30,
            "total_time_minutes": 45,
            "perform_time_minutes": 20,
            "nutrition": {
                "calories": "420 kcal",
                "proteinContent": "30 g",
            },
            "aggregate_rating": {
                "ratingValue": "4.5",
                "reviewCount": "12",
            },
            "keywords": "schnell, vegetarisch",
            "author": "Anna",
            "date_published": "2026-01-15",
            "steps": [{"position": 0, "text": "Alles mischen."}],
        },
        cookies=cookies,
    )
    assert create.status_code == 201
    data = create.json()
    assert data["description"] == "Kurze Zusammenfassung"
    assert data["prep_time_minutes"] == 15
    assert data["cook_time_minutes"] == 30
    assert data["total_time_minutes"] == 45
    assert data["perform_time_minutes"] == 20
    assert data["nutrition"] == {
        "calories": "420 kcal",
        "proteinContent": "30 g",
    }
    assert data["aggregate_rating"] == {
        "ratingValue": "4.5",
        "reviewCount": "12",
    }
    assert data["keywords"] == "schnell, vegetarisch"
    assert data["author"] == "Anna"
    assert data["date_published"] == "2026-01-15"

    detail = await client.get(f"/api/recipes/{data['id']}", cookies=cookies)
    assert detail.status_code == 200
    d = detail.json()
    assert d["description"] == "Kurze Zusammenfassung"
    assert d["prep_time_minutes"] == 15
    assert d["nutrition"] == {
        "calories": "420 kcal",
        "proteinContent": "30 g",
    }
    assert d["date_published"] == "2026-01-15"


@pytest.mark.asyncio
async def test_create_recipe_without_new_fields_returns_nulls(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "nonewfields")
    cookies = auth["cookies"]

    create = await client.post(
        "/api/recipes",
        json={
            "title": "Schlicht",
            "steps": [{"position": 0, "text": "Los."}],
        },
        cookies=cookies,
    )
    assert create.status_code == 201
    data = create.json()
    assert data["description"] is None
    assert data["prep_time_minutes"] is None
    assert data["cook_time_minutes"] is None
    assert data["total_time_minutes"] is None
    assert data["perform_time_minutes"] is None
    assert data["nutrition"] is None
    assert data["aggregate_rating"] is None
    assert data["keywords"] is None
    assert data["author"] is None
    assert data["date_published"] is None


@pytest.mark.asyncio
async def test_update_recipe_sets_new_fields(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "setnewfields")
    cookies = auth["cookies"]

    create = await client.post(
        "/api/recipes",
        json={
            "title": "Mutable",
            "steps": [{"position": 0, "text": "Start."}],
        },
        cookies=cookies,
    )
    assert create.status_code == 201
    recipe_id = create.json()["id"]

    set_resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={
            "description": "Neu",
            "cook_time_minutes": 25,
            "keywords": "schnell",
        },
        cookies=cookies,
    )
    assert set_resp.status_code == 200
    data = set_resp.json()
    assert data["description"] == "Neu"
    assert data["cook_time_minutes"] == 25
    assert data["keywords"] == "schnell"


@pytest.mark.asyncio
async def test_import_recipe_returns_steps(client: AsyncClient) -> None:
    auth = await _register(client, "importsteps")
    cookies = auth["cookies"]

    mock_recipe = ScrapedRecipe(
        title="Import Steps",
        ingredients=["100g Mehl"],
        instructions="Schritt A\nSchritt B",
        servings=2,
        source_url="https://www.example.com/import-steps",
        source_domain="www.example.com",
    )
    with patch("app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe):
        resp = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.example.com/import-steps"},
            cookies=cookies,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "steps" in data
    assert len(data["steps"]) == 1
    assert data["steps"][0]["position"] == 0
    assert data["steps"][0]["text"] == "Schritt A\nSchritt B"
    assert data["steps"][0]["name"] is None
    assert "instructions" not in data


@pytest.mark.asyncio
async def test_import_recipe_returns_extended_fields_and_diet_tags(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth = await _register(client, "importextended")
    cookies = auth["cookies"]

    # Find a diet tag id for resolution
    from sqlalchemy import text

    veg_result = await db_session.execute(
        text("SELECT id FROM tags WHERE name = 'VegetarianDiet'")
    )
    veg_tag_id = veg_result.scalar_one()

    from datetime import date

    mock_recipe = ScrapedRecipe(
        title="Extended Import",
        ingredients=["500g Rüebli"],
        instructions="Schälen.\nKochen.",
        image_url="https://img.example/ext.jpg",
        servings=4,
        source_url="https://www.example.com/extended",
        source_domain="www.example.com",
        description="Ein gesundes Rüebli-Rezept.",
        prep_time_minutes=15,
        cook_time_minutes=30,
        total_time_minutes=45,
        perform_time_minutes=10,
        nutrients={"calories": "120 kcal", "fat": "5 g"},
        cuisine="Schweizerisch",
        category="Hauptgericht",
        keywords="gesund, einfach",
        author="Betty Bossi",
        date_published=date(2024, 1, 15),
        ratings=4.5,
        suitable_for_diet=["https://schema.org/VegetarianDiet"],
    )
    with patch("app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe):
        resp = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.example.com/extended"},
            cookies=cookies,
        )
    assert resp.status_code == 200
    data = resp.json()

    # Basic fields
    assert data["title"] == "Extended Import"
    assert data["source_url"] == "https://www.example.com/extended"
    assert data["is_partial"] is False

    # Extended fields
    assert data["description"] == "Ein gesundes Rüebli-Rezept."
    assert data["prep_time_minutes"] == 15
    assert data["cook_time_minutes"] == 30
    assert data["total_time_minutes"] == 45
    assert data["perform_time_minutes"] == 10
    assert data["author"] == "Betty Bossi"
    assert data["date_published"] == "2024-01-15"
    assert data["keywords"] == "gesund, einfach"
    assert data["ratings"] == 4.5

    # suitable_for_diet resolution
    assert "suitable_for_diet_tag_ids" in data
    assert veg_tag_id in data["suitable_for_diet_tag_ids"]


@pytest.mark.asyncio
async def test_import_recipe_partial_scrape_populates_description(
    client: AsyncClient,
) -> None:
    auth = await _register(client, "importpartialdesc")
    cookies = auth["cookies"]

    mock_recipe = ScrapedRecipe(
        title="Partial",
        ingredients=[],
        instructions="",
        servings=4,
        source_url="https://www.example.com/partial",
        source_domain="www.example.com",
        is_partial=True,
        description="Eine kurze Beschreibung.",
    )
    with patch("app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe):
        resp = await client.post(
            "/api/recipes/import",
            json={"url": "https://www.example.com/partial"},
            cookies=cookies,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_partial"] is True
    assert data["description"] == "Eine kurze Beschreibung."
