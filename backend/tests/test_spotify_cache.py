"""Request budgets, expiry, and authorization for transient Spotify reuse."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import respx
from cryptography.fernet import Fernet
from sqlalchemy import event
from sqlalchemy.orm import Session
from test_albums import ALBUM_A, mock_refresh, owner, page, raw_album
from test_monthly_mosaics import (
    PATH,
    TRACK_A,
    TRACK_B,
    mock_top,
    monthly_owner,
    saved_snapshot,
    set_scope,
    track,
)
from test_persistent_auth import login
from test_profile_update_api import create_owner

from app.api.routes.auth import SPOTIFY_ME_URL
from app.core.config import settings
from app.models import SpotifyConnection
from app.services import monthly_mosaic, spotify_cache
from app.services.spotify import API_URL, TOKEN_URL

__all__ = ["monthly_owner", "owner"]


@pytest.fixture
def cache_clock(monkeypatch):
    clock = [spotify_cache.monotonic()]
    monkeypatch.setattr(spotify_cache, "monotonic", lambda: clock[0])
    return clock


@pytest.mark.parametrize("track_count", [43, 50])
@pytest.mark.parametrize(
    "warm_token", [False, True], ids=["refresh-needed", "cached-token"]
)
@respx.mock
def test_generation_and_warm_reopen_obey_spotify_request_budget(
    monthly_owner, track_count, warm_token
):
    client, factory, user_id = monthly_owner
    if warm_token:

        async def seed_valid_token():
            async with factory() as db:
                connection = await db.get(SpotifyConnection, user_id)
                spotify_cache.access_tokens.put(
                    spotify_cache.connection_key(connection),
                    "cached-access",
                    spotify_cache.monotonic() + 3600,
                )

        asyncio.run(seed_valid_token())
    refresh = mock_refresh(expires_in=3600)
    top = mock_top(
        [
            track(f"{index:022d}", id=f"{index + 100:022d}", name=f"Song {index}")
            for index in range(track_count)
        ]
    )
    result = client.post(PATH, json={})
    assert result.status_code == 201
    data = result.json()
    assert len(data["artwork"]) == track_count
    assert len(data["tiles"]) == 84  # The refined pumpkin repeats existing songs.
    assert datetime.fromisoformat(data["artwork_expires_at"]) > datetime.now(UTC)
    for tile in data["tiles"]:
        album_id, track_id = tile["spotifyAlbumId"], tile["spotifyTrackId"]
        metadata = data["artwork"][f"{album_id}:{track_id}"]
        assert metadata["imageUrl"] == "https://i.scdn.co/image/test"
        assert metadata["representativeTrack"]["id"] == track_id
        details = client.get(
            f"{PATH}/{data['id']}/albums/{album_id}", params={"track_id": track_id}
        )
        assert details.status_code == 200 and details.json() == metadata
    archive = client.get(PATH)
    assert archive.json()["items"] == [saved_snapshot(result)]
    assert "artwork" not in archive.text
    assert "server-access" not in result.text and "original-refresh" not in result.text
    repeated = client.post(PATH, json={})
    assert repeated.status_code == 200
    assert saved_snapshot(repeated) == saved_snapshot(result)
    assert refresh.call_count == (0 if warm_token else 1)
    assert top.call_count == 1
    expected = [("GET", f"{API_URL}/me/top/tracks")]
    if not warm_token:
        expected.insert(0, ("POST", TOKEN_URL))
    assert [
        (call.request.method, str(call.request.url).split("?")[0])
        for call in respx.calls
    ] == expected


@respx.mock
def test_metadata_expiry_fetches_original_song_with_reused_token(
    monthly_owner, cache_clock
):
    client, _, _ = monthly_owner
    refresh = mock_refresh(expires_in=3600)
    top = mock_top([track()])
    data = client.post(PATH, json={}).json()
    path = f"{PATH}/{data['id']}/albums/{ALBUM_A}"
    assert client.get(path).status_code == 200
    cache_clock[0] += spotify_cache.METADATA_TTL
    song = respx.get(f"{API_URL}/tracks/{TRACK_A}").mock(
        return_value=httpx.Response(200, json=track(name="Updated title"))
    )
    assert client.get(path).json()["representativeTrack"]["name"] == "Updated title"
    assert client.get(path).status_code == 200
    assert refresh.call_count == top.call_count == song.call_count == 1
    assert client.get(PATH).json()["items"] == [
        saved_snapshot(httpx.Response(200, json=data))
    ]


@respx.mock
def test_generation_reuses_access_for_next_month_and_preserves_old_songs(
    monthly_owner,
    monkeypatch,
):
    client, _, _ = monthly_owner
    refresh = mock_refresh(expires_in=3600)
    top = mock_top([track(id=TRACK_A, name="October song")])
    october = client.post(PATH, json={}).json()
    monkeypatch.setattr(
        monthly_mosaic, "utc_now", lambda: datetime(2026, 11, 1, tzinfo=UTC)
    )
    top.mock(
        return_value=httpx.Response(
            200, json={"items": [track(id=TRACK_B, name="November song")]}
        )
    )
    november = client.post(PATH, json={}).json()
    assert (
        november["artwork"][f"{ALBUM_A}:{TRACK_B}"]["representativeTrack"]["name"]
        == "November song"
    )
    old = client.get(f"{PATH}/{october['id']}/albums/{ALBUM_A}")
    assert old.json()["representativeTrack"]["id"] == TRACK_A
    assert refresh.call_count == 1 and top.call_count == 2


@respx.mock
def test_warm_metadata_still_checks_membership_owner_session_and_scope(monthly_owner):
    client, factory, user_id = monthly_owner
    refresh = mock_refresh(expires_in=3600)
    top = mock_top([track()])
    data = client.post(PATH, json={}).json()
    path = f"{PATH}/{data['id']}/albums/{ALBUM_A}"
    assert client.get(path).status_code == 200
    assert client.get(path, params={"track_id": TRACK_B}).status_code == 404
    set_scope(factory, user_id, "user-library-read")
    assert client.get(path).status_code == 403
    set_scope(factory, user_id)
    token = client.cookies.get("mosaic_session")
    create_owner(
        factory,
        account_id=uuid4().hex,
        username=f"cache_{uuid4().hex[:8]}",
        token="cache-visitor",
    )
    client.cookies.set("mosaic_session", "cache-visitor")
    assert client.get(path).status_code == 404
    client.cookies.set("mosaic_session", token)
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set("mosaic_session", token)
    assert client.get(path).status_code == 401
    assert refresh.call_count == top.call_count == 1


@respx.mock
def test_reconnect_invalidates_cached_token_and_metadata(monthly_owner):
    client, factory, user_id = monthly_owner
    refresh = mock_refresh(expires_in=3600)
    mock_top([track()])
    data = client.post(PATH, json={}).json()

    async def reconnect():
        async with factory() as db, db.begin():
            connection = await db.get(SpotifyConnection, user_id)
            connection.encrypted_refresh_token = (
                Fernet(settings.token_encryption_key)
                .encrypt(b"reconnected-refresh")
                .decode()
            )

    asyncio.run(reconnect())
    song = respx.get(f"{API_URL}/tracks/{TRACK_A}").mock(
        return_value=httpx.Response(200, json=track())
    )
    assert client.get(f"{PATH}/{data['id']}/albums/{ALBUM_A}").status_code == 200
    assert refresh.call_count == 2 and song.call_count == 1
    assert b"refresh_token=reconnected-refresh" in refresh.calls[-1].request.content


@respx.mock
def test_access_token_reused_until_expiry_margin(owner, cache_clock):
    client, _, _ = owner
    refresh = mock_refresh(expires_in=3600)
    albums = respx.get(f"{API_URL}/me/albums").mock(
        return_value=httpx.Response(200, json=page([]))
    )
    assert client.get("/api/me/albums").status_code == 200
    cache_clock[0] += 3569
    assert client.get("/api/me/albums").status_code == 200
    assert refresh.call_count == 1
    cache_clock[0] += 1
    assert client.get("/api/me/albums").status_code == 200
    assert refresh.call_count == 2 and albums.call_count == 3


@pytest.mark.parametrize("expires_in", [None, "3600", True, -1, 0])
@respx.mock
def test_unknown_token_lifetime_is_not_cached(owner, expires_in):
    client, _, _ = owner
    refresh = mock_refresh(expires_in=expires_in)
    respx.get(f"{API_URL}/me/albums").mock(
        return_value=httpx.Response(200, json=page([]))
    )
    assert client.get("/api/me/albums").status_code == 200
    assert client.get("/api/me/albums").status_code == 200
    assert refresh.call_count == 2


@respx.mock
def test_cached_token_401_refreshes_once_and_reuses_replacement(owner):
    client, _, _ = owner
    refresh = mock_refresh(expires_in=3600)
    albums = respx.get(f"{API_URL}/me/albums").mock(
        return_value=httpx.Response(200, json=page([]))
    )
    assert client.get("/api/me/albums").status_code == 200
    refresh.mock(
        return_value=httpx.Response(
            200, json={"access_token": "replacement", "expires_in": 3600}
        )
    )
    albums.mock(side_effect=[httpx.Response(401), httpx.Response(200, json=page([]))])
    assert client.get("/api/me/albums").status_code == 200
    assert refresh.call_count == 2
    assert albums.calls[-1].request.headers["Authorization"] == "Bearer replacement"
    albums.mock(return_value=httpx.Response(200, json=page([])))
    assert client.get("/api/me/albums").status_code == 200
    assert refresh.call_count == 2
    # A permanently rejected replacement is evicted, with no unbounded retry.
    albums.mock(return_value=httpx.Response(401))
    assert client.get("/api/me/albums").status_code == 403
    assert refresh.call_count == 3
    albums.mock(return_value=httpx.Response(200, json=page([])))
    assert client.get("/api/me/albums").status_code == 200
    assert refresh.call_count == 4


@respx.mock
def test_refresh_cache_is_not_published_before_commit(owner):
    client, _, _ = owner
    refresh = mock_refresh(expires_in=3600, refresh_token="rotated-refresh")
    albums = respx.get(f"{API_URL}/me/albums").mock(
        return_value=httpx.Response(200, json=page([]))
    )
    commits = 0

    def fail_refresh_commit(session):
        nonlocal commits
        commits += 1
        if commits == 2:  # Owner read commits first, then refreshed credentials.
            raise RuntimeError("simulated commit failure")

    event.listen(Session, "before_commit", fail_refresh_commit)
    try:
        with pytest.raises(RuntimeError, match="simulated commit failure"):
            client.get("/api/me/albums")
    finally:
        event.remove(Session, "before_commit", fail_refresh_commit)
    assert albums.call_count == 0
    assert client.get("/api/me/albums").status_code == 200
    assert refresh.call_count == 2
    assert b"refresh_token=original-refresh" in refresh.calls[-1].request.content


@respx.mock
def test_oauth_access_token_is_reused_after_login(database_client):
    client, _ = database_client
    token = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "oauth-access",
                "refresh_token": "oauth-refresh",
                "expires_in": 3600,
                "scope": "user-library-read",
            },
        )
    )
    respx.get(SPOTIFY_ME_URL).mock(
        return_value=httpx.Response(200, json={"account_id": uuid4().hex})
    )
    assert login(client).headers["location"].endswith("/dashboard")
    albums = respx.get(f"{API_URL}/me/albums").mock(
        return_value=httpx.Response(200, json=page([raw_album()]))
    )
    response = client.get("/api/me/albums")
    assert response.status_code == 200
    assert token.call_count == 1
    assert albums.calls[0].request.headers["Authorization"] == "Bearer oauth-access"
    assert "oauth-access" not in response.text and "oauth-refresh" not in response.text


def test_cache_has_bounded_size_and_fixed_expiry(cache_clock):
    cache = spotify_cache.TTLCache[str, str](2)
    cache.put("first", "one", cache_clock[0] + 10)
    cache.put("second", "two", cache_clock[0] + 20)
    assert cache.get("first") == "one"
    cache.put("third", "three", cache_clock[0] + 20)
    assert cache.get("second") is None
    cache_clock[0] += 10
    assert cache.get("first") is None  # Reading must not extend the lifetime.
    assert cache.get("third") == "three"


@respx.mock
def test_concurrent_requests_share_one_committed_refresh(owner):
    client, _, _ = owner
    refresh = mock_refresh(expires_in=3600, refresh_token="rotated-once")
    albums = respx.get(f"{API_URL}/me/albums").mock(
        return_value=httpx.Response(200, json=page([]))
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: client.get("/api/me/albums"), range(2)))
    assert all(response.status_code == 200 for response in responses)
    assert refresh.call_count == 1 and albums.call_count == 2


@respx.mock
def test_concurrent_401_responses_share_one_replacement(owner):
    client, _, _ = owner
    refresh = mock_refresh(expires_in=3600)
    albums = respx.get(f"{API_URL}/me/albums").mock(
        return_value=httpx.Response(200, json=page([]))
    )
    assert client.get("/api/me/albums").status_code == 200
    refresh.mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "replacement-access",
                "refresh_token": "rotated",
                "expires_in": 3600,
            },
        )
    )
    both_rejected = asyncio.Event()
    rejected = 0

    async def reject_original(request):
        nonlocal rejected
        if request.headers["Authorization"] == "Bearer server-access":
            rejected += 1
            if rejected == 2:
                both_rejected.set()
            await asyncio.wait_for(both_rejected.wait(), timeout=5)
            return httpx.Response(401)
        assert request.headers["Authorization"] == "Bearer replacement-access"
        return httpx.Response(200, json=page([]))

    albums.mock(side_effect=reject_original)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: client.get("/api/me/albums"), range(2)))
    assert all(response.status_code == 200 for response in responses)
    assert refresh.call_count == 2 and albums.call_count == 5


@respx.mock
def test_failed_song_fallback_is_not_cached(monthly_owner):
    client, _, _ = monthly_owner
    refresh = mock_refresh(expires_in=3600)
    mock_top([track()])
    data = client.post(PATH, json={}).json()
    spotify_cache.monthly_metadata.clear()
    song = respx.get(f"{API_URL}/tracks/{TRACK_A}").mock(
        return_value=httpx.Response(404)
    )
    album = respx.get(f"{API_URL}/albums/{ALBUM_A}").mock(
        return_value=httpx.Response(200, json=raw_album())
    )
    path = f"{PATH}/{data['id']}/albums/{ALBUM_A}"
    assert client.get(path).json()["trackDetailsUnavailable"] is True
    song.mock(return_value=httpx.Response(200, json=track()))
    assert client.get(path).json()["representativeTrack"]["id"] == TRACK_A
    assert client.get(path).json()["trackDetailsUnavailable"] is False
    assert song.call_count == 2 and album.call_count == 1 and refresh.call_count == 1
