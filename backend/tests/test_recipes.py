from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.scraper import ScrapedRecipe


async def _register(client: AsyncClient, username: str = "testuser") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123"},
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
        json={"username": username, "password": "secret123"},
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
        json={"username": username, "password": "secret123"},
    )
    return {"cookies": login_resp.cookies, "data": login_resp.json()}


async def _create_recipe(
    client: AsyncClient, cookies, title="Test Recipe", **kwargs
) -> dict:
    body = {
        "title": title,
        "instructions": "Cook it.",
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

    with patch(
        "app.api.recipes.RecipeScraper.scrape", return_value=mock_recipe
    ):
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

    resp = await client.post(
        "/api/tags", json={"name": "Grillen"}, cookies=cookies
    )
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


# ----- Recipe detail test -----


@pytest.mark.asyncio
async def test_get_recipe_detail(client: AsyncClient) -> None:
    auth = await _register(client, "detailuser")
    cookies = auth["cookies"]

    recipe = await _create_recipe(
        client,
        cookies,
        title="Detail Recipe",
        instructions="Step 1. Step 2.",
        source_url="https://example.com/detail",
    )
    recipe_id = recipe["id"]

    resp = await client.get(f"/api/recipes/{recipe_id}", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Detail Recipe"
    assert data["instructions"] == "Step 1. Step 2."
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


# ----- Recipe update test -----


@pytest.mark.asyncio
async def test_update_recipe(client: AsyncClient) -> None:
    auth = await _register(client, "updateuser")
    cookies = auth["cookies"]

    recipe = await _create_recipe(
        client, cookies, title="Old Title", instructions="Old instr."
    )
    recipe_id = recipe["id"]

    resp = await client.put(
        f"/api/recipes/{recipe_id}",
        json={
            "title": "New Title",
            "instructions": "New instr.",
            "servings": 5,
        },
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "New Title"
    assert data["instructions"] == "New instr."
    assert data["servings"] == 5


@pytest.mark.asyncio
async def test_update_recipe_tags(client: AsyncClient) -> None:
    auth = await _register(client, "tagupdateuser")
    cookies = auth["cookies"]

    tag1 = await client.post(
        "/api/tags", json={"name": "Vegetarisch"}, cookies=cookies
    )
    tag2 = await client.post(
        "/api/tags", json={"name": "Schnell"}, cookies=cookies
    )
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


# ----- Soft-delete tests -----


@pytest.mark.asyncio
async def test_admin_can_soft_delete_recipe(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    auth = await _register_and_set_role(
        client, db_session, "deladmin", role="admin"
    )
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

    auth_member = await _join_household(
        client, db_session, "delmember2", household_id
    )
    member_cookies = auth_member["cookies"]

    recipe = await _create_recipe(client, member_cookies, title="No Delete")
    recipe_id = recipe["id"]

    resp = await client.delete(
        f"/api/recipes/{recipe_id}", cookies=member_cookies
    )
    assert resp.status_code == 403


# ----- Favorite tests -----


@pytest.mark.asyncio
async def test_toggle_favorite(client: AsyncClient) -> None:
    auth = await _register(client, "favuser")
    cookies = auth["cookies"]

    recipe = await _create_recipe(client, cookies, title="Fav Recipe")
    recipe_id = recipe["id"]

    resp = await client.post(
        f"/api/recipes/{recipe_id}/favorite", cookies=cookies
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["recipe_id"] == recipe_id

    detail = await client.get(f"/api/recipes/{recipe_id}", cookies=cookies)
    assert detail.json()["is_favorited"] is True

    resp2 = await client.post(
        f"/api/recipes/{recipe_id}/favorite", cookies=cookies
    )
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
async def test_search_recipes_by_instructions(client: AsyncClient) -> None:
    auth = await _register(client, "searchinstuser")
    cookies = auth["cookies"]

    await _create_recipe(
        client,
        cookies,
        title="Risotto",
        instructions="Use Arborio rice and Parmesan.",
    )
    await _create_recipe(
        client,
        cookies,
        title="Pasta",
        instructions="Boil water and cook.",
    )

    resp = await client.get(
        "/api/recipes", params={"search": "Arborio"}, cookies=cookies
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Risotto"


# ----- Tag filter tests -----


@pytest.mark.asyncio
async def test_filter_recipes_by_tag(client: AsyncClient) -> None:
    auth = await _register(client, "tagfilteruser")
    cookies = auth["cookies"]

    tag = await client.post(
        "/api/tags", json={"name": "Vegan"}, cookies=cookies
    )
    tag_id = tag.json()["id"]

    r1 = await _create_recipe(client, cookies, title="Salad")
    await _create_recipe(client, cookies, title="Steak")

    await client.put(
        f"/api/recipes/{r1['id']}",
        json={"tag_ids": [tag_id]},
        cookies=cookies,
    )

    resp = await client.get(
        "/api/recipes", params={"tag_id": tag_id}, cookies=cookies
    )
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

    list_resp = await client.get(
        f"/api/recipes/{recipe_id}/notes", cookies=cookies
    )
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

    auth2 = await _join_household(
        client, db_session, "noteuser2", household_id
    )
    cookies2 = auth2["cookies"]

    list_resp = await client.get(
        f"/api/recipes/{recipe_id}/notes", cookies=cookies2
    )
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

    auth2 = await _join_household(
        client, db_session, "hnoteuser2", household_id
    )
    cookies2 = auth2["cookies"]

    list_resp = await client.get(
        f"/api/recipes/{recipe_id}/notes", cookies=cookies2
    )
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

    list_resp = await client.get(
        f"/api/recipes/{recipe_id}/notes", cookies=cookies
    )
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
