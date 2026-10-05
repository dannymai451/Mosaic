"""Owner profile PATCH API tests against migrated PostgreSQL."""

import asyncio
from datetime import UTC, datetime, timedelta


def create_owner(factory, *, account_id: str, username: str, token: str):
    from app.repositories import sessions
    from app.services.accounts import create_user_with_profile

    async def scenario():
        async with factory() as db:
            user, _ = await create_user_with_profile(
                db,
                spotify_account_id=account_id,
                username=username,
                display_name="Initial name",
            )
            async with db.begin():
                await sessions.create(
                    db,
                    token=token,
                    user_id=user.id,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            return user.id

    return asyncio.run(scenario())


def test_profile_patch_updates_owner_fields_and_keeps_omitted_fields(database_client):
    client, factory = database_client
    create_owner(factory, account_id="profile-owner", username="owner_one", token="owner-cookie")
    client.cookies.set("mosaic_session", "owner-cookie")

    response = client.patch(
        "/api/me/profile",
        json={
            "username": "new_owner",
            "display_name": "  Updated Display  ",
            "bio": "Music, memories, and mixtapes.",
            "visibility": "public",
            "theme": {"preset": "plum"},
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "username": "new_owner",
        "displayName": "Updated Display",
        "images": [],
        "bio": "Music, memories, and mixtapes.",
        "visibility": "public",
        "theme": {"preset": "plum"},
    }

    partial = client.patch("/api/me/profile", json={"bio": "Changed bio"})
    assert partial.status_code == 200
    assert partial.json()["username"] == "new_owner"
    assert partial.json()["displayName"] == "Updated Display"
    assert partial.json()["bio"] == "Changed bio"
    assert partial.json()["visibility"] == "public"
    assert partial.json()["theme"] == {"preset": "plum"}


def test_profile_patch_requires_owner_session_and_rejects_supplied_identity(database_client):
    client, factory = database_client
    create_owner(factory, account_id="secure-owner", username="secure_user", token="secure-cookie")

    assert client.patch("/api/me/profile", json={"bio": "No session"}).status_code == 401

    client.cookies.set("mosaic_session", "secure-cookie")
    forged = client.patch(
        "/api/me/profile", json={"bio": "Attempted takeover", "user_id": "someone-else"}
    )
    assert forged.status_code == 422
    assert forged.json()["detail"][0]["type"] == "extra_forbidden"

    from app.repositories import profiles

    async def read_bio():
        async with factory() as db:
            return (await profiles.get_by_username(db, "secure_user")).bio

    assert asyncio.run(read_bio()) == ""


def test_profile_patch_reports_taken_username_without_changing_owner(database_client):
    client, factory = database_client
    create_owner(factory, account_id="first-owner", username="first_user", token="first-cookie")
    create_owner(factory, account_id="second-owner", username="second_user", token="second-cookie")
    client.cookies.set("mosaic_session", "first-cookie")

    response = client.patch("/api/me/profile", json={"username": "second_user"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Username is unavailable"

    from app.repositories import profiles

    async def read_username():
        async with factory() as db:
            return (await profiles.get_by_user_id(db, (await profiles.get_by_username(db, "first_user")).user_id)).username

    assert asyncio.run(read_username()) == "first_user"


def test_profile_patch_validates_values_and_rejects_empty_patch(database_client):
    client, factory = database_client
    create_owner(factory, account_id="validated-owner", username="valid_user", token="valid-cookie")
    client.cookies.set("mosaic_session", "valid-cookie")

    cases = [
        ({}, 422),
        ({"username": "Bad Name"}, 422),
        ({"username": "no"}, 422),
        ({"display_name": "  "}, 422),
        ({"display_name": "x" * 256}, 422),
        ({"bio": "x" * 501}, 422),
        ({"visibility": "friends"}, 422),
        ({"theme": {"preset": "neon"}}, 422),
        ({"theme": {"preset": "paper", "background": "url"}}, 422),
        ({"bio": None}, 422),
        ({"username": "valid_user"}, 200),
    ]
    for body, expected_status in cases:
        response = client.patch("/api/me/profile", json=body)
        assert response.status_code == expected_status, (body, response.text)
