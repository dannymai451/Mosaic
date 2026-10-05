"""Phase 4 HTTP behavior with migrated PostgreSQL and mocked Spotify."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import respx
from cryptography.fernet import Fernet

from app.core.config import settings
from app.models import Session, SpotifyConnection
from app.repositories import profiles, sessions, spotify_connections
from app.repositories.sessions import token_digest
from app.services.accounts import create_user_with_profile
from app.services.spotify import API_URL, TOKEN_URL

ALBUM_A = "4aawyAB9vmqN3uQ7FjRGTy"
ALBUM_B = "2up3OPMp9Tb4dAKM2erWXQ"


def raw_album(album_id=ALBUM_A):
    return {
        "id": album_id,
        "name": "Test album",
        "artists": [{"name": "Test artist", "id": "unused"}],
        "images": [{"url": "https://i.scdn.co/image/test"}],
        "release_date": "2020-01-01",
        "total_tracks": 10,
        "tracks": {"items": []},
        "available_markets": ["US"],
        "external_urls": {"spotify": "https://example.com/do-not-forward"},
    }


def page(items, *, total=None, next_page=None):
    return {
        "items": [{"album": item, "added_at": "unused"} for item in items],
        "total": len(items) if total is None else total,
        "next": next_page,
    }


@pytest.fixture
def owner(database_client):
    client, factory = database_client
    cookie = uuid4().hex

    async def create():
        async with factory() as db:
            user, _ = await create_user_with_profile(
                db,
                spotify_account_id=f"albums-{cookie}",
                username=f"albums_{cookie[:20]}",
                display_name="Album owner",
            )
            async with db.begin():
                await sessions.create(
                    db,
                    token=cookie,
                    user_id=user.id,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
                await spotify_connections.upsert(
                    db,
                    user_id=user.id,
                    encrypted_refresh_token=Fernet(settings.token_encryption_key)
                    .encrypt(b"original-refresh")
                    .decode(),
                    scopes="user-read-private user-library-read",
                )
            return user.id

    user_id = asyncio.run(create())
    client.cookies.set("mosaic_session", cookie)
    return client, factory, user_id


def mock_refresh(**extra):
    return respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "server-access", **extra}
        )
    )


@respx.mock
def test_twenty_albums_pagination_normalized_and_no_tokens(owner):
    client, _, _ = owner
    refresh = mock_refresh()
    first = respx.get(f"{API_URL}/me/albums", params={"limit": 20, "offset": 0}).mock(
        return_value=httpx.Response(
            200,
            json=page(
                [raw_album(f"{i:022d}") for i in range(20)],
                total=21,
                next_page="https://untrusted.example/next",
            ),
        )
    )
    second = respx.get(f"{API_URL}/me/albums", params={"limit": 20, "offset": 20}).mock(
        return_value=httpx.Response(200, json=page([raw_album(ALBUM_B)], total=21))
    )
    result = client.get("/api/me/albums")
    assert result.status_code == 200
    assert len(result.json()["items"]) == 20
    assert result.json()["nextOffset"] == 20
    assert set(result.json()["items"][0]) == {
        "id",
        "name",
        "artists",
        "imageUrl",
        "spotifyUrl",
        "releaseDate",
        "totalTracks",
    }
    assert result.json()["items"][0]["artists"] == ["Test artist"]
    assert (
        result.json()["items"][0]["spotifyUrl"]
        == "https://open.spotify.com/album/0000000000000000000000"
    )
    assert "server-access" not in result.text and "original-refresh" not in result.text
    assert result.headers["cache-control"] == "no-store"
    assert first.calls[0].request.headers["Authorization"] == "Bearer server-access"
    assert b"grant_type=refresh_token" in refresh.calls[0].request.content
    assert client.get("/api/me/albums?offset=20").json()["nextOffset"] is None
    assert second.call_count == 1


@respx.mock
def test_selection_persists_order_removal_and_owner_isolation(owner):
    client, factory, user_id = owner
    refresh = mock_refresh()
    contains = respx.get(
        f"{API_URL}/me/library/contains",
        params={"uris": f"spotify:album:{ALBUM_B},spotify:album:{ALBUM_A}"},
    ).mock(return_value=httpx.Response(200, json=[True, True]))
    assert client.get("/api/me/featured-albums").json() == {"albumIds": []}
    result = client.put(
        "/api/me/featured-albums", json={"album_ids": [ALBUM_B, ALBUM_A]}
    )
    assert result.status_code == 200
    assert result.json() == {"albumIds": [ALBUM_B, ALBUM_A]}
    assert contains.call_count == 1

    async def stored():
        async with factory() as db:
            return (await profiles.get_by_user_id(db, user_id)).featured_album_ids

    assert asyncio.run(stored()) == [ALBUM_B, ALBUM_A]
    assert client.get("/api/me/featured-albums").json() == result.json()
    # Removal does not depend on Spotify or mutate the user's Spotify library.
    assert (
        client.put("/api/me/featured-albums", json={"album_ids": [ALBUM_A]}).status_code
        == 200
    )
    assert refresh.call_count == 1
    assert asyncio.run(stored()) == [ALBUM_A]

    async def other_owner():
        async with factory() as db:
            user, _ = await create_user_with_profile(
                db,
                spotify_account_id=uuid4().hex,
                username=f"other_{uuid4().hex[:20]}",
                display_name="Other",
            )
            async with db.begin():
                await sessions.create(
                    db,
                    token="other-album-cookie",
                    user_id=user.id,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )

    asyncio.run(other_owner())
    client.cookies.set("mosaic_session", "other-album-cookie")
    assert client.get("/api/me/featured-albums").json() == {"albumIds": []}
    assert (
        client.put("/api/me/featured-albums", json={"album_ids": []}).status_code == 200
    )
    assert asyncio.run(stored()) == [ALBUM_A]


@respx.mock
def test_unsaved_or_invalid_selection_does_not_write(owner):
    client, _, _ = owner
    mock_refresh()
    respx.get(f"{API_URL}/me/library/contains").mock(
        return_value=httpx.Response(200, json=[True, False])
    )
    result = client.put(
        "/api/me/featured-albums", json={"album_ids": [ALBUM_A, ALBUM_B]}
    )
    assert result.status_code == 422
    assert result.json() == {"detail": "album_not_saved"}
    assert client.get("/api/me/featured-albums").json() == {"albumIds": []}
    for body in [
        {},
        {"album_ids": None},
        {"album_ids": [ALBUM_A, ALBUM_A]},
        {"album_ids": ["bad"]},
        {"album_ids": [f"{i:022d}" for i in range(101)]},
        {"album_ids": [], "user_id": str(uuid4())},
    ]:
        assert client.put("/api/me/featured-albums", json=body).status_code == 422
    for query in ["limit=0", "limit=51", "offset=-1"]:
        assert client.get(f"/api/me/albums?{query}").status_code == 422


@respx.mock
def test_empty_library_and_missing_artwork(owner):
    client, _, _ = owner
    mock_refresh()
    route = respx.get(f"{API_URL}/me/albums").mock(
        return_value=httpx.Response(200, json=page([]))
    )
    assert client.get("/api/me/albums").json() == {
        "items": [],
        "total": 0,
        "nextOffset": None,
    }
    raw = raw_album()
    raw["images"] = []
    raw["artists"] = []
    raw["name"] = ""
    route.mock(return_value=httpx.Response(200, json=page([raw])))
    album = client.get("/api/me/albums").json()["items"][0]
    assert album["imageUrl"] is None and album["artists"] == []
    assert album["name"] == "Unavailable album"


@respx.mock
def test_expired_access_retry_and_rotated_refresh_survive_upstream_failure(owner):
    client, factory, user_id = owner
    refresh = respx.post(TOKEN_URL).mock(
        side_effect=[
            httpx.Response(
                200, json={"access_token": "expired", "refresh_token": "rotated-one"}
            ),
            httpx.Response(
                200, json={"access_token": "renewed", "refresh_token": "rotated-two"}
            ),
        ]
    )
    route = respx.get(f"{API_URL}/me/albums").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(
                429, headers={"Retry-After": "12"}, json={"access_token": "do-not-leak"}
            ),
        ]
    )
    result = client.get("/api/me/albums", headers={"Origin": "http://127.0.0.1:3000"})
    assert result.status_code == 429
    assert result.headers["access-control-expose-headers"] == "Retry-After"
    assert result.headers["retry-after"] == "12"
    assert result.json() == {"detail": "spotify_rate_limited"}
    assert route.call_count == 2 and refresh.call_count == 2
    assert route.calls[1].request.headers["Authorization"] == "Bearer renewed"
    assert b"refresh_token=rotated-one" in refresh.calls[1].request.content

    async def stored():
        async with factory() as db:
            return (await db.get(SpotifyConnection, user_id)).encrypted_refresh_token

    encrypted = asyncio.run(stored())
    assert encrypted != "rotated-two"
    assert (
        Fernet(settings.token_encryption_key).decrypt(encrypted.encode())
        == b"rotated-two"
    )


@pytest.mark.parametrize(
    "status, expected, code",
    [
        (403, 403, "spotify_reconnect_required"),
        (500, 502, "spotify_unavailable"),
        (429, 429, "spotify_rate_limited"),
        (401, 403, "spotify_reconnect_required"),
    ],
)
@respx.mock
def test_upstream_errors_are_safe_and_retry_is_bounded(owner, status, expected, code):
    client, _, _ = owner
    mock_refresh()
    route = respx.get(f"{API_URL}/me/albums").mock(
        return_value=httpx.Response(status, json={"secret": "provider-secret"})
    )
    result = client.get("/api/me/albums")
    assert result.status_code == expected
    assert result.json() == {"detail": code}
    assert route.call_count == (2 if status == 401 else 1)


@respx.mock
def test_malformed_upstream_and_network_errors(owner):
    client, _, _ = owner
    token = mock_refresh()
    albums = respx.get(f"{API_URL}/me/albums").mock(
        return_value=httpx.Response(200, text="not json")
    )
    assert client.get("/api/me/albums").json() == {"detail": "spotify_invalid_response"}
    albums.mock(return_value=httpx.Response(200, json={"items": None, "total": 0}))
    assert client.get("/api/me/albums").status_code == 502
    albums.mock(side_effect=httpx.ConnectError("Do not expose provider details"))
    assert client.get("/api/me/albums").json() == {"detail": "spotify_unavailable"}
    token.mock(
        return_value=httpx.Response(
            400, json={"error": "invalid_grant", "secret": "hidden"}
        )
    )
    assert client.get("/api/me/albums").json() == {
        "detail": "spotify_reconnect_required"
    }
    token.mock(
        return_value=httpx.Response(200, json={"refresh_token": "missing-access"})
    )
    assert client.get("/api/me/albums").status_code == 502


@respx.mock
def test_sessions_scopes_and_selected_details(owner):
    client, factory, user_id = owner

    async def prepare():
        async with factory() as db, db.begin():
            profile = await profiles.get_by_user_id(db, user_id)
            await profiles.set_featured_albums(db, profile, [ALBUM_A])

    asyncio.run(prepare())
    mock_refresh()
    respx.get(f"{API_URL}/albums/{ALBUM_A}").mock(
        return_value=httpx.Response(200, json=raw_album())
    )
    assert client.get(f"/api/me/albums/{ALBUM_A}").json()["name"] == "Test album"
    assert client.get(f"/api/me/albums/{ALBUM_B}").status_code == 404

    async def old_scope():
        async with factory() as db, db.begin():
            (await db.get(SpotifyConnection, user_id)).scopes = "user-read-private"

    asyncio.run(old_scope())
    assert client.get("/api/me/albums").json() == {
        "detail": "spotify_reconnect_required"
    }
    cookie = client.cookies.get("mosaic_session")

    async def expire():
        async with factory() as db, db.begin():
            (await db.get(Session, token_digest(cookie))).expires_at = datetime.now(
                UTC
            ) - timedelta(seconds=1)

    asyncio.run(expire())
    for path in [
        "/api/me/albums",
        "/api/me/featured-albums",
        f"/api/me/albums/{ALBUM_A}",
    ]:
        assert client.get(path).status_code == 401
    assert (
        client.put("/api/me/featured-albums", json={"album_ids": []}).status_code == 401
    )
    client.cookies.clear()
    assert client.get("/api/me/albums").status_code == 401
    client.cookies.set("mosaic_session", "unknown")
    assert client.get("/api/me/featured-albums").status_code == 401


def test_oauth_requests_library_scope(database_client):
    client, _ = database_client
    from urllib.parse import parse_qs, urlparse

    result = client.get("/api/auth/spotify/start", follow_redirects=False)
    assert (
        "user-library-read"
        in parse_qs(urlparse(result.headers["location"]).query)["scope"][0].split()
    )


@respx.mock
def test_large_selection_batches_and_failed_second_batch_are_atomic(owner):
    client, _, _ = owner
    mock_refresh()
    ids = [f"{i:022d}" for i in range(41)]
    contains = respx.get(f"{API_URL}/me/library/contains").mock(
        side_effect=[
            httpx.Response(200, json=[True] * 40),
            httpx.Response(429, headers={"Retry-After": "3"}),
        ]
    )
    assert (
        client.put("/api/me/featured-albums", json={"album_ids": ids}).status_code
        == 429
    )
    assert len(contains.calls[0].request.url.params["uris"].split(",")) == 40
    assert contains.calls[1].request.url.params["uris"] == f"spotify:album:{ids[40]}"
    assert client.get("/api/me/featured-albums").json() == {"albumIds": []}
    contains.mock(
        side_effect=[
            httpx.Response(200, json=[True] * 40),
            httpx.Response(200, json=[True]),
        ]
    )
    assert client.put("/api/me/featured-albums", json={"album_ids": ids}).json() == {
        "albumIds": ids
    }


@respx.mock
def test_malformed_membership_and_unreadable_refresh_are_safe(owner):
    client, factory, user_id = owner
    mock_refresh()
    contains = respx.get(f"{API_URL}/me/library/contains").mock(
        return_value=httpx.Response(200, json=[1])
    )
    for result in [[1], [], {"secret": "hidden"}]:
        contains.mock(return_value=httpx.Response(200, json=result))
        response = client.put("/api/me/featured-albums", json={"album_ids": [ALBUM_A]})
        assert response.status_code == 502
        assert response.json() == {"detail": "spotify_invalid_response"}
        assert client.get("/api/me/featured-albums").json() == {"albumIds": []}

    async def corrupt():
        async with factory() as db, db.begin():
            (
                await db.get(SpotifyConnection, user_id)
            ).encrypted_refresh_token = "not-a-fernet-token"

    asyncio.run(corrupt())
    assert client.get("/api/me/albums").json() == {
        "detail": "spotify_reconnect_required"
    }
