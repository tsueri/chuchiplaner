import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, username: str, invite_code: str | None = None):
    body = {"username": username, "password": "secret123"}
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
    assert member_household["slug"] == (
        await client.get("/api/household", cookies=admin_cookies)
    ).json()["slug"]
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
    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_get_household_member_list(client: AsyncClient) -> None:
    admin_resp = await _register(client, "admin3")
    admin_cookies = admin_resp.cookies
    invite_code = await _get_invite_code(client, admin_cookies)

    await _register(client, "member3a", invite_code)
    await _register(client, "member3b", invite_code)

    household = (
        await client.get("/api/household", cookies=admin_cookies)
    ).json()
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

    resp = await client.post(
        "/api/household/invite-code", cookies=admin_cookies
    )
    assert resp.status_code == 200
    new_code = resp.json()["invite_code"]
    assert new_code != old_code

    join_resp = await _register(client, "staleinvite", old_code)
    assert join_resp.status_code == 400

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

    resp = await client.post(
        "/api/household/invite-code", cookies=member_cookies
    )
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

    admin_household = (
        await client.get("/api/household", cookies=admin_cookies)
    ).json()
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

    household = (
        await client.get("/api/household", cookies=admin_cookies)
    ).json()
    assert household["name"] == "sluguser's Household"
    assert household["slug"] == "sluguser-s-household"
