import pytest
from httpx import AsyncClient

from app.services.household import generate_invite_code


async def _register(client: AsyncClient, username: str, invite_code: str | None = None):
    body: dict[str, str] = {
        "username": username,
        "password": "secret123",
        "admin_signup_code": "test-secret",
    }
    if invite_code is not None:
        body["invite_code"] = invite_code
    return await client.post("/api/auth/register", json=body)


async def _get_invite_code(client: AsyncClient, cookies) -> str:
    household = (await client.get("/api/household", cookies=cookies)).json()
    return household["invite_code"]


@pytest.mark.asyncio
async def test_register_creates_household(client: AsyncClient) -> None:
    response = await _register(client, "admin1")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin1"
    assert "id" in data

    cookies = response.cookies
    household_resp = await client.get("/api/household", cookies=cookies)
    assert household_resp.status_code == 200
    household = household_resp.json()
    assert "name" in household
    assert "slug" in household
    assert "invite_code" in household
    assert len(household["members"]) == 1
    assert household["members"][0]["username"] == "admin1"
    assert household["members"][0]["role"] == "admin"


@pytest.mark.asyncio
async def test_register_with_invite_code_joins_household(
    client: AsyncClient,
) -> None:
    admin_resp = await _register(client, "admin2")
    admin_cookies = admin_resp.cookies
    invite_code = await _get_invite_code(client, admin_cookies)

    member_resp = await _register(client, "member2", invite_code)
    assert member_resp.status_code == 200
    member_data = member_resp.json()
    assert member_data["username"] == "member2"

    member_cookies = member_resp.cookies
    member_household = (
        await client.get("/api/household", cookies=member_cookies)
    ).json()
    assert (
        member_household["slug"]
        == (await client.get("/api/household", cookies=admin_cookies)).json()["slug"]
    )
    assert len(member_household["members"]) == 2
    usernames = [m["username"] for m in member_household["members"]]
    assert "admin2" in usernames
    assert "member2" in usernames
    roles = {m["username"]: m["role"] for m in member_household["members"]}
    assert roles["admin2"] == "admin"
    assert roles["member2"] == "member"


@pytest.mark.asyncio
async def test_register_with_invalid_invite_code(
    client: AsyncClient,
) -> None:
    response = await _register(client, "badinvite", "NOT-REAL")
    assert response.status_code == 403
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_get_household_member_list(client: AsyncClient) -> None:
    admin_resp = await _register(client, "admin3")
    admin_cookies = admin_resp.cookies
    invite_code = await _get_invite_code(client, admin_cookies)

    await _register(client, "member3a", invite_code)
    await _register(client, "member3b", invite_code)

    household = (await client.get("/api/household", cookies=admin_cookies)).json()
    assert len(household["members"]) == 3


@pytest.mark.asyncio
async def test_member_can_access_household(client: AsyncClient) -> None:
    admin_resp = await _register(client, "admin4")
    admin_cookies = admin_resp.cookies
    invite_code = await _get_invite_code(client, admin_cookies)

    member_resp = await _register(client, "member4", invite_code)
    member_cookies = member_resp.cookies

    response = await client.get("/api/household", cookies=member_cookies)
    assert response.status_code == 200
    assert "members" in response.json()


@pytest.mark.asyncio
async def test_regenerate_invite_code_admin_only(
    client: AsyncClient,
) -> None:
    admin_resp = await _register(client, "admin5")
    admin_cookies = admin_resp.cookies
    old_code = await _get_invite_code(client, admin_cookies)

    resp = await client.post("/api/household/invite-code", cookies=admin_cookies)
    assert resp.status_code == 200
    new_code = resp.json()["invite_code"]
    assert new_code != old_code

    join_resp = await _register(client, "staleinvite", old_code)
    assert join_resp.status_code == 403

    join_resp2 = await _register(client, "newinvite", new_code)
    assert join_resp2.status_code == 200


@pytest.mark.asyncio
async def test_member_cannot_regenerate_invite_code(
    client: AsyncClient,
) -> None:
    admin_resp = await _register(client, "admin6")
    admin_cookies = admin_resp.cookies
    invite_code = await _get_invite_code(client, admin_cookies)

    member_resp = await _register(client, "member6", invite_code)
    member_cookies = member_resp.cookies

    resp = await client.post("/api/household/invite-code", cookies=member_cookies)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_remove_member(client: AsyncClient) -> None:
    admin_resp = await _register(client, "admin7")
    admin_cookies = admin_resp.cookies
    invite_code = await _get_invite_code(client, admin_cookies)

    member_resp = await _register(client, "member7", invite_code)
    member_data = member_resp.json()
    member_cookies = member_resp.cookies

    pre_resp = await client.get("/api/household", cookies=member_cookies)
    assert pre_resp.status_code == 200

    remove_resp = await client.delete(
        f"/api/household/members/{member_data['id']}",
        cookies=admin_cookies,
    )
    assert remove_resp.status_code == 200

    post_resp = await client.get("/api/household", cookies=member_cookies)
    assert post_resp.status_code == 401

    admin_household = (await client.get("/api/household", cookies=admin_cookies)).json()
    assert len(admin_household["members"]) == 1


@pytest.mark.asyncio
async def test_admin_cannot_remove_self(client: AsyncClient) -> None:
    admin_resp = await _register(client, "admin8")
    admin_cookies = admin_resp.cookies
    admin_data = admin_resp.json()

    resp = await client.delete(
        f"/api/household/members/{admin_data['id']}",
        cookies=admin_cookies,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_member_cannot_remove_other_member(
    client: AsyncClient,
) -> None:
    admin_resp = await _register(client, "admin9")
    admin_cookies = admin_resp.cookies
    invite_code = await _get_invite_code(client, admin_cookies)

    await _register(client, "member9a", invite_code)
    member_b_resp = await _register(client, "member9b", invite_code)
    member_b_cookies = member_b_resp.cookies
    member_a_data = (
        await client.post(
            "/api/auth/login",
            json={"username": "member9a", "password": "secret123"},
        )
    ).json()

    resp = await client.delete(
        f"/api/household/members/{member_a_data['id']}",
        cookies=member_b_cookies,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_no_household_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/household")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_slug_generated_from_household_name(
    client: AsyncClient,
) -> None:
    admin_resp = await _register(client, "sluguser")
    admin_cookies = admin_resp.cookies

    household = (await client.get("/api/household", cookies=admin_cookies)).json()
    assert household["name"] == "sluguser's Household"
    assert household["slug"] == "sluguser-s-household"


@pytest.mark.asyncio
async def test_household_has_default_size(client: AsyncClient) -> None:
    admin_resp = await _register(client, "sizetest")
    cookies = admin_resp.cookies

    household = (await client.get("/api/household", cookies=cookies)).json()
    assert household["default_size"] == 1


@pytest.mark.asyncio
async def test_admin_can_update_household(client: AsyncClient) -> None:
    admin_resp = await _register(client, "updateadmin")
    cookies = admin_resp.cookies

    resp = await client.put(
        "/api/household",
        json={"name": "New Name", "default_size": 4},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["slug"] == "new-name"
    assert data["default_size"] == 4


@pytest.mark.asyncio
async def test_member_cannot_update_household(client: AsyncClient) -> None:
    admin_resp = await _register(client, "updateadmin2")
    admin_cookies = admin_resp.cookies
    invite_code = await _get_invite_code(client, admin_cookies)

    member_resp = await _register(client, "updatemember", invite_code)
    member_cookies = member_resp.cookies

    resp = await client.put(
        "/api/household",
        json={"default_size": 5},
        cookies=member_cookies,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_household_creation_seeds_28_meal_slots(
    client: AsyncClient,
) -> None:
    admin_resp = await _register(client, "slottest")
    cookies = admin_resp.cookies

    resp = await client.get("/api/household/meal-template", cookies=cookies)
    assert resp.status_code == 200
    slots = resp.json()
    assert len(slots) == 28

    days = {s["day_of_week"] for s in slots}
    assert days == set(range(7))

    meal_types = {s["meal_type"] for s in slots}
    assert meal_types == {"breakfast", "lunch", "dinner", "dessert"}

    for s in slots:
        assert s["active"] is True
        assert s["household_id"] is not None


@pytest.mark.asyncio
async def test_deactivate_saturday_breakfast(client: AsyncClient) -> None:
    admin_resp = await _register(client, "deactivetest")
    cookies = admin_resp.cookies

    slots = (await client.get("/api/household/meal-template", cookies=cookies)).json()
    sat_breakfast = next(
        s for s in slots if s["day_of_week"] == 5 and s["meal_type"] == "breakfast"
    )
    assert sat_breakfast["active"] is True

    resp = await client.put(
        "/api/household/meal-template",
        json={
            "slots": [
                {
                    "day_of_week": 5,
                    "meal_type": "breakfast",
                    "active": False,
                }
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    slots2 = (await client.get("/api/household/meal-template", cookies=cookies)).json()
    sat_breakfast2 = next(
        s for s in slots2 if s["day_of_week"] == 5 and s["meal_type"] == "breakfast"
    )
    assert sat_breakfast2["active"] is False


@pytest.mark.asyncio
async def test_change_default_portions_for_dinner(client: AsyncClient) -> None:
    admin_resp = await _register(client, "portiontest")
    cookies = admin_resp.cookies

    resp = await client.put(
        "/api/household/meal-template",
        json={
            "slots": [
                {
                    "day_of_week": day,
                    "meal_type": "dinner",
                    "default_portions": 6,
                }
                for day in range(7)
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 200

    slots = (await client.get("/api/household/meal-template", cookies=cookies)).json()
    for s in slots:
        if s["meal_type"] == "dinner":
            assert s["default_portions"] == 6


@pytest.mark.asyncio
async def test_cannot_deactivate_all_slots(client: AsyncClient) -> None:
    admin_resp = await _register(client, "nodeactest")
    cookies = admin_resp.cookies

    slots = (await client.get("/api/household/meal-template", cookies=cookies)).json()
    resp = await client.put(
        "/api/household/meal-template",
        json={
            "slots": [
                {
                    "day_of_week": s["day_of_week"],
                    "meal_type": s["meal_type"],
                    "active": False,
                }
                for s in slots
            ]
        },
        cookies=cookies,
    )
    assert resp.status_code == 400
    assert "at least one" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_member_cannot_update_meal_template(
    client: AsyncClient,
) -> None:
    admin_resp = await _register(client, "tpltadmin")
    admin_cookies = admin_resp.cookies
    invite_code = await _get_invite_code(client, admin_cookies)

    member_resp = await _register(client, "tpltmember", invite_code)
    member_cookies = member_resp.cookies

    resp = await client.put(
        "/api/household/meal-template",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "meal_type": "breakfast",
                    "active": False,
                }
            ]
        },
        cookies=member_cookies,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_meal_template_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/household/meal-template")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_default_size_does_not_overwrite_template_portions(
    client: AsyncClient,
) -> None:
    admin_resp = await _register(client, "sizeinittst")
    cookies = admin_resp.cookies

    slots = (await client.get("/api/household/meal-template", cookies=cookies)).json()
    for s in slots:
        assert s["default_portions"] == 1

    await client.put(
        "/api/household/meal-template",
        json={
            "slots": [
                {
                    "day_of_week": day,
                    "meal_type": "dinner",
                    "default_portions": 6,
                }
                for day in range(7)
            ]
        },
        cookies=cookies,
    )

    await client.put(
        "/api/household",
        json={"default_size": 3},
        cookies=cookies,
    )

    household = (await client.get("/api/household", cookies=cookies)).json()
    assert household["default_size"] == 3

    slots2 = (await client.get("/api/household/meal-template", cookies=cookies)).json()
    for s in slots2:
        if s["meal_type"] == "dinner":
            assert s["default_portions"] == 6, (
                f"dinner template should keep override 6, got {s['default_portions']}"
            )
        else:
            assert s["default_portions"] == 1, (
                f"non-dinner template should stay at 1, got {s['default_portions']}"
            )


@pytest.mark.asyncio
async def test_export_household_data(client: AsyncClient) -> None:
    response = await _register(client, "exportadmin")
    assert response.status_code == 200
    cookies = response.cookies

    export_resp = await client.get("/api/household/export", cookies=cookies)
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"] == "application/json"
    assert "attachment" in export_resp.headers.get("content-disposition", "")

    data = export_resp.json()
    assert "household" in data
    assert data["household"]["name"] is not None
    assert data["household"]["slug"] is not None
    assert "members" in data
    assert len(data["members"]) == 1
    assert "password_hash" not in str(data)
    assert "meal_template" in data
    assert len(data["meal_template"]) == 28
    assert "recipes" in data
    assert "recipes_as_jsonld" in data
    assert data["recipes_as_jsonld"]["@context"] == "https://schema.org"
    assert "@graph" in data["recipes_as_jsonld"]
    assert isinstance(data["recipes_as_jsonld"]["@graph"], list)
    assert "week_plans" in data
    assert "inventory" in data
    assert "grocery_lists" in data
    assert "aliases" in data


@pytest.mark.asyncio
async def test_export_no_password_hashes(client: AsyncClient) -> None:
    response = await _register(client, "exportadmin2")
    assert response.status_code == 200
    cookies = response.cookies

    export_resp = await client.get("/api/household/export", cookies=cookies)
    assert export_resp.status_code == 200

    import json

    raw = export_resp.text
    data = json.loads(raw)
    raw_lower = raw.lower()
    assert "password_hash" not in raw_lower
    assert "password" not in data.get("members", [{}])[0]


@pytest.mark.asyncio
async def test_export_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/household/export")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_alias_duplicate_returns_409(client: AsyncClient) -> None:
    resp = await _register(client, "aliasdup")
    cookies = resp.cookies

    ing = await client.post(
        "/api/ingredients", json={"name": "Pouletbrust"}, cookies=cookies
    )
    ingredient_id = ing.json()["id"]

    first = await client.post(
        "/api/household/aliases",
        json={"ingredient_id": ingredient_id, "alias_name": "Hähnchenbrust"},
        cookies=cookies,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/household/aliases",
        json={"ingredient_id": ingredient_id, "alias_name": "Hähnchenbrust"},
        cookies=cookies,
    )
    assert second.status_code == 409
    assert "detail" in second.json()


@pytest.mark.asyncio
async def test_alias_case_insensitive_duplicate_returns_409(
    client: AsyncClient,
) -> None:
    resp = await _register(client, "aliascase")
    cookies = resp.cookies

    ing = await client.post(
        "/api/ingredients", json={"name": "Pouletbrust"}, cookies=cookies
    )
    ingredient_id = ing.json()["id"]

    first = await client.post(
        "/api/household/aliases",
        json={"ingredient_id": ingredient_id, "alias_name": "Hähnchenbrust"},
        cookies=cookies,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/household/aliases",
        json={"ingredient_id": ingredient_id, "alias_name": "hähnchenbrust"},
        cookies=cookies,
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_alias_fresh_returns_201(client: AsyncClient) -> None:
    resp = await _register(client, "aliasfresh")
    cookies = resp.cookies

    ing = await client.post(
        "/api/ingredients", json={"name": "Pouletbrust"}, cookies=cookies
    )
    ingredient_id = ing.json()["id"]

    response = await client.post(
        "/api/household/aliases",
        json={"ingredient_id": ingredient_id, "alias_name": "Hähnchenbrust"},
        cookies=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["household_id"] is not None
    assert data["alias_name"] == "Hähnchenbrust"
    assert data["ingredient_id"] == ingredient_id


@pytest.mark.asyncio
async def test_alias_cross_household_same_alias_returns_201(
    client: AsyncClient,
) -> None:
    resp1 = await _register(client, "household1")
    cookies1 = resp1.cookies

    resp2 = await _register(client, "household2")
    cookies2 = resp2.cookies

    ing = await client.post(
        "/api/ingredients", json={"name": "Pouletbrust"}, cookies=cookies1
    )
    ingredient_id = ing.json()["id"]

    first = await client.post(
        "/api/household/aliases",
        json={"ingredient_id": ingredient_id, "alias_name": "Hähnchenbrust"},
        cookies=cookies1,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/household/aliases",
        json={"ingredient_id": ingredient_id, "alias_name": "Hähnchenbrust"},
        cookies=cookies2,
    )
    assert second.status_code == 201


@pytest.mark.asyncio
async def test_export_jsonld_full_recipe(client: AsyncClient) -> None:
    resp = await _register(client, "jsonlduser")
    assert resp.status_code == 200
    cookies = resp.cookies

    tags_resp = await client.get("/api/tags", cookies=cookies)
    tags_list = tags_resp.json()

    def _tag_id(name: str, group: str) -> int:
        for t in tags_list:
            if t["name"] == name and t["group"] == group:
                return t["id"]
        raise ValueError(f"Tag {name}/{group} not found")

    cat_id = _tag_id("Hauptgericht", "category")
    cui_id = _tag_id("Italienisch", "cuisine")
    diet_id = _tag_id("VegetarianDiet", "diet")

    ing_resp = await client.post(
        "/api/ingredients", json={"name": "Spaghetti"}, cookies=cookies
    )
    ing_id = ing_resp.json()["id"]

    recipe_body = {
        "title": "Spaghetti Napoli",
        "description": "Einfaches Pastagericht",
        "image_url": "https://example.com/napoli.jpg",
        "servings": 4,
        "author": "Chef Koch",
        "date_published": "2025-06-01",
        "prep_time_minutes": 10,
        "cook_time_minutes": 20,
        "total_time_minutes": 30,
        "perform_time_minutes": 15,
        "nutrition": {"calories": "400 kcal", "carbohydrateContent": "50 g"},
        "aggregate_rating": {"ratingValue": 4.5, "reviewCount": 10},
        "keywords": "Pasta, Tomate, Schnell",
        "steps": [
            {"text": "Wasser kochen.", "name": "Vorbereitung"},
            {"text": "Spaghetti kochen und Sauce zubereiten."},
        ],
        "ingredients": [
            {
                "ingredient_id": ing_id,
                "quantity": 500.0,
                "unit": "g",
                "order_index": 0,
            }
        ],
    }
    create_resp = await client.post("/api/recipes", json=recipe_body, cookies=cookies)
    assert create_resp.status_code == 201
    recipe_id = create_resp.json()["id"]

    await client.put(
        f"/api/recipes/{recipe_id}",
        json={"tag_ids": [cat_id, cui_id, diet_id]},
        cookies=cookies,
    )

    export_resp = await client.get("/api/household/export", cookies=cookies)
    assert export_resp.status_code == 200
    data = export_resp.json()

    assert "recipes_as_jsonld" in data
    jsonld = data["recipes_as_jsonld"]
    assert jsonld["@context"] == "https://schema.org"
    assert len(jsonld["@graph"]) == 1

    recipe_node = jsonld["@graph"][0]
    assert recipe_node["@type"] == "Recipe"
    assert recipe_node["name"] == "Spaghetti Napoli"
    assert recipe_node["description"] == "Einfaches Pastagericht"
    assert recipe_node["image"] == "https://example.com/napoli.jpg"
    assert recipe_node["recipeYield"] == "4"
    assert recipe_node["author"] == {"@type": "Person", "name": "Chef Koch"}
    assert recipe_node["datePublished"] == "2025-06-01"
    assert recipe_node["prepTime"] == "PT10M"
    assert recipe_node["cookTime"] == "PT20M"
    assert recipe_node["totalTime"] == "PT30M"
    assert recipe_node["performTime"] == "PT15M"
    assert recipe_node["nutrition"] == {
        "calories": "400 kcal",
        "carbohydrateContent": "50 g",
    }
    assert recipe_node["aggregateRating"] == {
        "ratingValue": 4.5,
        "reviewCount": 10,
    }
    assert recipe_node["keywords"] == "Pasta, Tomate, Schnell"
    assert recipe_node["recipeIngredient"] == ["Spaghetti"]
    assert len(recipe_node["recipeInstructions"]) == 2
    assert recipe_node["recipeInstructions"][0] == {
        "@type": "HowToStep",
        "text": "Wasser kochen.",
        "name": "Vorbereitung",
    }
    assert recipe_node["recipeInstructions"][1] == {
        "@type": "HowToStep",
        "text": "Spaghetti kochen und Sauce zubereiten.",
    }
    assert recipe_node["recipeCategory"] == "Hauptgericht"
    assert recipe_node["recipeCuisine"] == "Italienisch"
    assert recipe_node["suitableForDiet"] == ["https://schema.org/VegetarianDiet"]
    assert recipe_node["identifier"] == recipe_id
    assert "season" not in recipe_node


@pytest.mark.asyncio
async def test_update_household_slug_bad_pattern(client: AsyncClient) -> None:
    admin_resp = await _register(client, "patternadmin")
    cookies = admin_resp.cookies

    resp = await client.put(
        "/api/household",
        json={"slug": "Bad Slug!"},
        cookies=cookies,
    )
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_update_household_slug_too_long(client: AsyncClient) -> None:
    admin_resp = await _register(client, "longadmin")
    cookies = admin_resp.cookies

    resp = await client.put(
        "/api/household",
        json={"slug": "x" * 65},
        cookies=cookies,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_household_slug_collision(client: AsyncClient) -> None:
    admin1_resp = await _register(client, "collision1")
    admin1_cookies = admin1_resp.cookies

    admin2_resp = await _register(client, "collision2")
    admin2_cookies = admin2_resp.cookies

    household1 = (
        await client.get("/api/household", cookies=admin1_cookies)
    ).json()
    hh1_slug = household1["slug"]

    resp = await client.put(
        "/api/household",
        json={"slug": hh1_slug},
        cookies=admin2_cookies,
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data
    assert "vergeben" in str(data["detail"]).lower()


@pytest.mark.asyncio
async def test_update_household_slug_valid(client: AsyncClient) -> None:
    admin_resp = await _register(client, "validadmin")
    cookies = admin_resp.cookies

    resp = await client.put(
        "/api/household",
        json={"slug": "valid-slug"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "valid-slug"


@pytest.mark.asyncio
async def test_update_household_name_only_auto_slug(client: AsyncClient) -> None:
    admin_resp = await _register(client, "auto-admin")
    cookies = admin_resp.cookies

    resp = await client.put(
        "/api/household",
        json={"name": "New Auto Name"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Auto Name"
    assert data["slug"] == "new-auto-name"


def test_generate_invite_code_returns_32_char_hex() -> None:
    code = generate_invite_code()
    assert len(code) == 32
    assert all(c in "0123456789abcdef" for c in code)


def test_generate_invite_code_no_collisions() -> None:
    codes = {generate_invite_code() for _ in range(10_000)}
    assert len(codes) == 10_000


def test_generate_invite_code_docstring_mentions_unguessable() -> None:
    doc = generate_invite_code.__doc__
    assert doc is not None
    assert "unguessable" in doc.lower()
