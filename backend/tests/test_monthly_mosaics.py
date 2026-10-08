"""Monthly listening snapshots with real migrations and mocked Spotify."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from cryptography.fernet import Fernet
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from test_albums import ALBUM_A, ALBUM_B, mock_refresh, owner, raw_album
from test_profile_update_api import create_owner

from app.core.config import settings
from app.models import MonthlyMosaic, Profile, SpotifyConnection
from app.repositories import monthly_mosaics, profiles
from app.services import monthly_mosaic, spotify_cache
from app.services.mosaic import expand_preset
from app.services.spotify import API_URL

__all__ = ["owner"]
PATH = "/api/me/monthly-mosaics"
ALBUM_C = "0000000000000000000003"
TRACK_A = "0000000000000000000101"
TRACK_B = "0000000000000000000102"


def saved_snapshot(response):
    """Compare durable layout fields independently of transient generation data."""
    return {
        key: value
        for key, value in response.json().items()
        if key not in {"artwork", "artwork_expires_at"}
    }


def track(album_id=ALBUM_A, **changes):
    return {
        "id": TRACK_A,
        "name": "Representative song",
        "artists": [{"name": "Track artist"}],
        "album": raw_album(album_id),
        "is_local": False,
        **changes,
    }


def set_scope(factory, user_id, scopes="user-read-private user-top-read"):
    async def change():
        async with factory() as db, db.begin():
            (await db.get(SpotifyConnection, user_id)).scopes = scopes

    asyncio.run(change())


@pytest.fixture
def monthly_owner(owner, monkeypatch):
    client, factory, user_id = owner
    set_scope(factory, user_id)
    monkeypatch.setattr(
        monthly_mosaic, "utc_now", lambda: datetime(2026, 10, 5, 12, tzinfo=UTC)
    )
    return client, factory, user_id


def mock_top(items):
    return respx.get(
        f"{API_URL}/me/top/tracks",
        params={"time_range": "short_term", "limit": 50, "offset": 0},
    ).mock(return_value=httpx.Response(200, json={"items": items}))


@respx.mock
def test_generate_ranks_album_tracks_and_saves_ids_only(monthly_owner):
    client, factory, user_id = monthly_owner
    assert client.get(PATH).json() == {"current_month": "2026-10", "items": []}
    refresh = mock_refresh()
    top = mock_top(
        [
            track(ALBUM_B),
            track(ALBUM_A, id=TRACK_B),
            track(ALBUM_A),
            track(ALBUM_C),
            track(ALBUM_B, is_local=True),
            None,
            track(album=None),
            track(ALBUM_C, is_playable=False),
        ]
    )
    result = client.post(PATH, json={})
    assert result.status_code == 201
    data = saved_snapshot(result)
    assert data["album_ids"] == [ALBUM_A, ALBUM_B, ALBUM_C]
    assert data["source_track_count"] == 4
    assert data["listening_basis"] == "spotify_short_term"
    assert data["month"] == "2026-10"
    assert data["generated_at"] == "2026-10-05T12:00:00Z"
    assert {item["spotifyAlbumId"] for item in data["tiles"]} == set(data["album_ids"])
    assert (
        data["tiles"]
        == monthly_mosaic.monthly_layout(
            date(2026, 10, 1),
            data["album_ids"],
            {ALBUM_A: [TRACK_B, TRACK_A], ALBUM_B: [TRACK_A], ALBUM_C: [TRACK_A]},
        )[1].model_dump()["tiles"]
    )
    assert result.headers["cache-control"] == "no-store"
    for hidden in [
        "server-access",
        "original-refresh",
        "profile_id",
        "user_id",
    ]:
        assert hidden not in result.text
    archive = client.get(PATH)
    assert "imageUrl" not in archive.text and "Test album" not in archive.text
    assert refresh.call_count == 1 and top.call_count == 1

    async def stored():
        async with factory() as db, db.begin():
            profile = await profiles.get_by_user_id(db, user_id)
            records = await monthly_mosaics.list_for_profile(db, profile.id)
            assert len(records) == 1
            record = records[0]
            assert record.album_ids == data["album_ids"]
            assert record.tiles == data["tiles"]
            assert record.representative_track_ids == {
                ALBUM_A: TRACK_B,
                ALBUM_B: TRACK_A,
                ALBUM_C: TRACK_A,
            }
            assert record.month == date(2026, 10, 1)
            assert record.generated_at.tzinfo is not None
            assert profile.featured_album_ids == []

    asyncio.run(stored())
    # Monthly data works with the top scope alone and needs no saved library.
    assert client.get("/api/me/albums").status_code == 403


@respx.mock
def test_repeat_is_immutable_without_spotify_and_removal_does_not_prune(monthly_owner):
    client, factory, user_id = monthly_owner
    refresh = mock_refresh()
    top = mock_top([track()])
    original = saved_snapshot(client.post(PATH, json={}))
    set_scope(factory, user_id, "user-read-private")
    repeated = client.post(PATH, json={})
    assert repeated.status_code == 200 and saved_snapshot(repeated) == original
    assert refresh.call_count == 1 and top.call_count == 1

    async def prepare_featured():
        async with factory() as db, db.begin():
            profile = await profiles.get_by_user_id(db, user_id)
            await profiles.set_featured_albums(db, profile, [ALBUM_A])

    asyncio.run(prepare_featured())
    assert (
        client.put("/api/me/featured-albums", json={"album_ids": []}).status_code == 200
    )
    assert client.get(PATH).json()["items"] == [original]
    # No edit/delete/activation route can overwrite snapshots.
    for method in ["put", "patch", "delete"]:
        assert client.request(method, PATH, json={}).status_code == 405


@respx.mock
def test_utc_rollover_preserves_previous_month_and_shared_shape(
    monthly_owner, monkeypatch
):
    client, factory, user_id = monthly_owner
    mock_refresh()
    top = mock_top([track()])
    monkeypatch.setattr(
        monthly_mosaic, "utc_now", lambda: datetime(2026, 10, 31, 23, 59, tzinfo=UTC)
    )
    october = saved_snapshot(client.post(PATH, json={}))
    # Still October locally, but the canonical period is November in UTC.
    monkeypatch.setattr(
        monthly_mosaic,
        "utc_now",
        lambda: datetime(2026, 10, 31, 20, 1, tzinfo=timezone(timedelta(hours=-4))),
    )
    top.mock(return_value=httpx.Response(200, json={"items": [track(ALBUM_B)]}))
    november = client.post(PATH, json={})
    assert november.status_code == 201
    november = saved_snapshot(november)
    assert november["month"] == "2026-11"
    assert november["album_ids"] == [ALBUM_B]
    assert november["preset_key"] != october["preset_key"]
    assert client.get(PATH).json() == {
        "current_month": "2026-11",
        "items": [november, october],
    }
    other_token = f"monthly-other-{uuid4()}"
    other_user = create_owner(
        factory,
        account_id=uuid4().hex,
        username=f"month_{uuid4().hex[:12]}",
        token=other_token,
    )

    # Attach a top-scope connection by copying only the encrypted fixture value.
    async def connection():
        async with factory() as db, db.begin():
            original = await db.get(SpotifyConnection, user_id)
            db.add(
                SpotifyConnection(
                    user_id=other_user,
                    scopes=original.scopes,
                    encrypted_refresh_token=original.encrypted_refresh_token,
                )
            )

    asyncio.run(connection())
    client.cookies.set("mosaic_session", other_token)
    other = client.post(PATH, json={})
    assert other.status_code == 201
    assert other.json()["preset_key"] == november["preset_key"]
    assert client.get(PATH).json()["items"] == [saved_snapshot(other)]


@respx.mock
def test_request_crossing_midnight_keeps_generation_time_and_month_consistent(
    monthly_owner, monkeypatch
):
    client, _, _ = monthly_owner
    mock_refresh()
    requested_at = datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC)
    monkeypatch.setattr(monthly_mosaic, "utc_now", lambda: requested_at)

    def after_midnight(request):
        monkeypatch.setattr(
            monthly_mosaic,
            "utc_now",
            lambda: datetime(2026, 11, 1, 0, 0, 1, tzinfo=UTC),
        )
        return httpx.Response(200, json={"items": [track()]})

    respx.get(f"{API_URL}/me/top/tracks").mock(side_effect=after_midnight)
    response = client.post(PATH, json={})
    assert response.status_code == 201
    snapshot = saved_snapshot(response)
    assert snapshot["month"] == "2026-10"
    assert snapshot["generated_at"] == "2026-10-31T23:59:59Z"
    assert client.get(PATH).json() == {"current_month": "2026-11", "items": [snapshot]}


@respx.mock
def test_refresh_rotation_commits_even_when_refreshed_scope_requires_reconnect(
    monthly_owner,
):
    client, factory, user_id = monthly_owner
    mock_refresh(refresh_token="rotated-without-top-scope", scope="user-read-private")
    response = client.post(PATH, json={})
    assert response.status_code == 403
    assert response.json() == {"detail": "spotify_reconnect_required"}
    assert client.get(PATH).json()["items"] == []

    async def stored():
        async with factory() as db:
            connection = await db.get(SpotifyConnection, user_id)
            assert connection.scopes == "user-read-private"
            return connection.encrypted_refresh_token

    encrypted = asyncio.run(stored())
    assert (
        Fernet(settings.token_encryption_key).decrypt(encrypted.encode())
        == b"rotated-without-top-scope"
    )


@respx.mock
def test_snapshot_details_guard_owner_and_membership(monthly_owner):
    client, factory, _ = monthly_owner
    refresh = mock_refresh()
    mock_top([track()])
    snapshot = client.post(PATH, json={}).json()
    spotify_cache.monthly_metadata.clear()  # Exercise a cold detail lookup.
    path = f"{PATH}/{snapshot['id']}/albums/{ALBUM_A}"
    details = respx.get(f"{API_URL}/albums/{ALBUM_A}").mock(
        return_value=httpx.Response(200, json=raw_album())
    )
    song = respx.get(f"{API_URL}/tracks/{TRACK_A}").mock(
        return_value=httpx.Response(200, json=track())
    )
    result = client.get(path)
    assert result.status_code == 200
    assert result.json()["name"] == "Test album"
    assert result.json()["imageUrl"] == "https://i.scdn.co/image/test"
    assert result.json()["spotifyUrl"] == f"https://open.spotify.com/album/{ALBUM_A}"
    assert result.json()["representativeTrack"] == {
        "id": TRACK_A,
        "name": "Representative song",
        "artists": ["Track artist"],
        "spotifyUrl": f"https://open.spotify.com/track/{TRACK_A}",
    }
    assert result.json()["trackDetailsUnavailable"] is False
    assert "server-access" not in result.text and "refresh" not in result.text
    assert result.headers["cache-control"] == "no-store"
    assert client.get(f"{PATH}/{snapshot['id']}/albums/{ALBUM_B}").status_code == 404
    assert client.get(f"{PATH}/{uuid4()}/albums/{ALBUM_A}").status_code == 404
    create_owner(
        factory,
        account_id=uuid4().hex,
        username=f"visitor_{uuid4().hex[:12]}",
        token="monthly-visitor",
    )
    client.cookies.set("mosaic_session", "monthly-visitor")
    assert client.get(path).status_code == 404
    assert client.get(PATH).json()["items"] == []
    assert refresh.call_count == 2 and song.call_count == 1
    assert details.call_count == 0
    for token in [None, "unknown"]:
        client.cookies.clear()
        if token:
            client.cookies.set("mosaic_session", token)
        assert client.get(PATH).status_code == 401
        assert client.post(PATH, json={}).status_code == 401
        assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    "field", ["month", "profile_id", "user_id", "preset_key", "album_ids", "tiles"]
)
def test_generation_rejects_forged_or_caller_selected_fields(monthly_owner, field):
    client, _, _ = monthly_owner
    assert client.post(PATH, json={field: "forged"}).status_code == 422
    assert client.get(PATH).json()["items"] == []


@respx.mock
def test_missing_scope_requests_reconnect_and_oauth_includes_top_scope(owner):
    client, _, _ = owner
    assert client.post(PATH, json={}).json() == {"detail": "spotify_reconnect_required"}
    assert client.get(PATH).json()["items"] == []
    result = client.get("/api/auth/spotify/start", follow_redirects=False)
    scopes = parse_qs(urlparse(result.headers["location"]).query)["scope"][0].split()
    assert "user-top-read" in scopes


@pytest.mark.parametrize(
    "items",
    [
        [],
        [None],
        [track(is_local=True)],
        [track(is_playable=False)],
        [track(album=None)],
    ],
)
@respx.mock
def test_no_recent_listening_never_creates_empty_snapshot(monthly_owner, items):
    client, _, _ = monthly_owner
    mock_refresh()
    mock_top(items)
    result = client.post(PATH, json={})
    assert result.status_code == 422
    assert result.json() == {"detail": "spotify_no_recent_listening"}
    assert client.get(PATH).json()["items"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"items": None},
        {"items": [3]},
        {"items": [track(album={"id": "bad"})]},
        {"items": [track(id="invalid")]},
        {"items": [track()] * 51},
    ],
)
@respx.mock
def test_malformed_top_tracks_return_safe_error(monthly_owner, payload):
    client, _, _ = monthly_owner
    mock_refresh()
    respx.get(f"{API_URL}/me/top/tracks").mock(
        return_value=httpx.Response(200, json=payload)
    )
    response = client.post(PATH, json={})
    assert response.status_code == 502
    assert response.json() == {"detail": "spotify_invalid_response"}
    assert client.get(PATH).json()["items"] == []


@pytest.mark.parametrize(
    "status,expected,code",
    [
        (401, 403, "spotify_reconnect_required"),
        (403, 403, "spotify_reconnect_required"),
        (429, 429, "spotify_rate_limited"),
        (500, 502, "spotify_unavailable"),
    ],
)
@respx.mock
def test_top_track_failures_do_not_archive_partial_data(
    monthly_owner, status, expected, code
):
    client, _, _ = monthly_owner
    refresh = mock_refresh()
    top = respx.get(f"{API_URL}/me/top/tracks").mock(
        return_value=httpx.Response(
            status, headers={"Retry-After": "9"}, json={"secret": "provider-secret"}
        )
    )
    response = client.post(PATH, json={})
    assert response.status_code == expected and response.json() == {"detail": code}
    assert refresh.call_count == top.call_count == (2 if status == 401 else 1)
    if status == 429:
        assert response.headers["retry-after"] == "9"
    assert client.get(PATH).json()["items"] == []


@respx.mock
def test_album_ids_trim_to_shape_capacity(monthly_owner):
    client, _, _ = monthly_owner
    mock_refresh()
    mock_top([track(f"{i:022d}") for i in range(50)])
    response = client.post(PATH, json={})
    assert response.status_code == 201
    data = response.json()
    assert data["source_track_count"] == 50
    assert len(data["album_ids"]) <= len(data["tiles"])
    assert set(data["album_ids"]) == {tile["spotifyAlbumId"] for tile in data["tiles"]}


@respx.mock
def test_snapshot_write_failure_rolls_back_and_db_constraints_cascade(
    monthly_owner, monkeypatch
):
    client, factory, user_id = monthly_owner
    mock_refresh()
    mock_top([track()])
    real_create = monthly_mosaics.create

    async def fail(*args, **kwargs):
        await real_create(*args, **kwargs)
        raise RuntimeError("write failed after flush")

    monkeypatch.setattr(monthly_mosaics, "create", fail)
    with pytest.raises(RuntimeError, match="write failed"):
        client.post(PATH, json={})
    assert client.get(PATH).json()["items"] == []
    monkeypatch.setattr(monthly_mosaics, "create", real_create)
    snapshot = client.post(PATH, json={}).json()

    async def constraints():
        async with factory() as db:
            async with db.begin():
                profile = await profiles.get_by_user_id(db, user_id)
                profile_id = profile.id
            for month, count in [
                (date(2026, 10, 1), 1),
                (date(2026, 11, 2), 1),
                (date(2026, 11, 1), 0),
            ]:
                with pytest.raises(IntegrityError):
                    async with db.begin():
                        await monthly_mosaics.create(
                            db,
                            profile_id,
                            month=month,
                            generated_at=datetime.now(UTC),
                            source_track_count=count,
                            album_ids=[ALBUM_A],
                            layout=expand_preset("heart", [ALBUM_A]),
                        )
            async with db.begin():
                await db.execute(delete(Profile).where(Profile.id == profile_id))
                assert await db.get(MonthlyMosaic, UUID(snapshot["id"])) is None

    asyncio.run(constraints())


@respx.mock
def test_concurrent_generation_stores_one_snapshot(monthly_owner):
    client, factory, user_id = monthly_owner
    mock_refresh()
    both_arrived = asyncio.Event()
    arrived = 0

    async def simultaneous_top(request):
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            both_arrived.set()
        await asyncio.wait_for(both_arrived.wait(), timeout=10)
        return httpx.Response(200, json={"items": [track()]})

    respx.get(f"{API_URL}/me/top/tracks").mock(side_effect=simultaneous_top)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: client.post(PATH, json={}), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 201]
    assert saved_snapshot(responses[0]) == saved_snapshot(responses[1])

    async def stored():
        async with factory() as db, db.begin():
            profile = await profiles.get_by_user_id(db, user_id)
            return list(
                await db.scalars(
                    select(MonthlyMosaic).where(MonthlyMosaic.profile_id == profile.id)
                )
            )

    assert len(asyncio.run(stored())) == 1


def test_october_pumpkin_is_bounded_and_does_not_extend_legacy_presets():
    from pydantic import ValidationError

    from app.schemas.mosaic import MosaicLayout
    from app.services.mosaic import PRESETS

    selected, pumpkin = monthly_mosaic.monthly_layout(
        date(2026, 10, 1), [ALBUM_A, ALBUM_B]
    )
    assert selected == [ALBUM_A, ALBUM_B]
    assert pumpkin.preset_key == "pumpkin"
    coordinates = {(tile.x, tile.y) for tile in pumpkin.tiles}
    assert 50 <= len(coordinates) == len(pumpkin.tiles) <= 100
    assert pumpkin.grid_width == pumpkin.grid_height == 12
    assert all(0 <= x < 12 and 0 <= y < 12 for x, y in coordinates)
    assert {(6, 0), (7, 0), (5, 1), (6, 1)} <= coordinates  # Bent stem.
    assert not {(3, 4), (8, 4), (2, 5), (9, 5), (5, 6), (6, 6)} & coordinates
    assert {(4, 8), (7, 8)} <= coordinates  # Teeth above the open grin.
    assert not {(x, 9) for x in range(3, 9)} & coordinates
    body = {(x, y) for x, y in coordinates if y >= 2}
    assert {(11 - x, y) for x, y in body} == body
    assert (
        monthly_mosaic.monthly_layout(date(2027, 10, 1), [ALBUM_A])[1].preset_key
        == "pumpkin"
    )
    assert (
        monthly_mosaic.monthly_layout(date(2026, 11, 1), [ALBUM_A])[1].preset_key
        != "pumpkin"
    )
    assert {preset.key for preset in PRESETS} == {
        "heart",
        "star",
        "music-note",
        "blank",
    }
    with pytest.raises(ValidationError):
        MosaicLayout.model_validate(pumpkin.model_dump())


@respx.mock
def test_legacy_october_snapshot_keeps_shape_and_has_no_fabricated_song(monthly_owner):
    client, factory, user_id = monthly_owner

    async def old_snapshot():
        async with factory() as db, db.begin():
            profile = await profiles.get_by_user_id(db, user_id)
            record = await monthly_mosaics.create(
                db,
                profile.id,
                month=date(2026, 10, 1),
                generated_at=datetime(2026, 10, 1, tzinfo=UTC),
                source_track_count=1,
                album_ids=[ALBUM_A],
                layout=expand_preset("heart", [ALBUM_A]),
            )
            assert record.representative_track_ids == {}
            return record.id

    snapshot_id = asyncio.run(old_snapshot())
    response = client.post(PATH, json={})
    assert response.status_code == 200
    assert response.json()["preset_key"] == "heart"
    mock_refresh()
    respx.get(f"{API_URL}/albums/{ALBUM_A}").mock(
        return_value=httpx.Response(200, json=raw_album())
    )
    details = client.get(f"{PATH}/{snapshot_id}/albums/{ALBUM_A}")
    assert details.status_code == 200
    assert details.json()["representativeTrack"] is None
    assert details.json()["trackDetailsUnavailable"] is False


@pytest.mark.parametrize(
    "failure",
    [
        "deleted",
        "network",
        "malformed",
        "malformed_album",
        "wrong_album",
        "wrong_track",
    ],
)
@respx.mock
def test_unavailable_or_unverified_song_preserves_album(monthly_owner, failure):
    client, _, _ = monthly_owner
    mock_refresh()
    mock_top([track()])
    snapshot = client.post(PATH, json={}).json()
    spotify_cache.monthly_metadata.clear()
    respx.get(f"{API_URL}/albums/{ALBUM_A}").mock(
        return_value=httpx.Response(200, json=raw_album())
    )
    song = respx.get(f"{API_URL}/tracks/{TRACK_A}")
    if failure == "network":
        song.mock(side_effect=httpx.ConnectError("provider-secret"))
    elif failure == "deleted":
        song.mock(return_value=httpx.Response(404))
    elif failure == "malformed":
        song.mock(return_value=httpx.Response(200, json={"secret": "hidden"}))
    elif failure == "malformed_album":
        song.mock(
            return_value=httpx.Response(
                200, json=track(album={**raw_album(), "images": [None]})
            )
        )
    elif failure == "wrong_album":
        song.mock(return_value=httpx.Response(200, json=track(ALBUM_B)))
    else:
        song.mock(return_value=httpx.Response(200, json=track(id=TRACK_B)))
    details = client.get(f"{PATH}/{snapshot['id']}/albums/{ALBUM_A}")
    assert details.status_code == 200
    assert details.json()["name"] == "Test album"
    assert details.json()["spotifyUrl"] == f"https://open.spotify.com/album/{ALBUM_A}"
    assert details.json()["representativeTrack"] is None
    assert details.json()["trackDetailsUnavailable"] is True
    assert "provider-secret" not in details.text and "hidden" not in details.text


@respx.mock
def test_song_rate_limit_stops_before_album_lookup(monthly_owner):
    client, _, _ = monthly_owner
    mock_refresh()
    mock_top([track()])
    snapshot = saved_snapshot(client.post(PATH, json={}))
    spotify_cache.monthly_metadata.clear()
    song = respx.get(f"{API_URL}/tracks/{TRACK_A}").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "10514"})
    )
    album = respx.get(f"{API_URL}/albums/{ALBUM_A}").mock(
        return_value=httpx.Response(200, json=raw_album())
    )
    result = client.get(f"{PATH}/{snapshot['id']}/albums/{ALBUM_A}")
    assert result.status_code == 429
    assert result.json() == {"detail": "spotify_rate_limited"}
    assert result.headers["retry-after"] == "10514"
    assert song.call_count == 1 and album.call_count == 0
    assert client.get(PATH).json()["items"] == [snapshot]


@respx.mock
def test_relinked_representative_song_requires_original_provenance(monthly_owner):
    client, factory, user_id = monthly_owner
    mock_refresh()
    mock_top([track()])
    snapshot = client.post(PATH, json={}).json()
    spotify_cache.monthly_metadata.clear()
    respx.get(f"{API_URL}/albums/{ALBUM_A}").mock(
        return_value=httpx.Response(200, json=raw_album())
    )
    song = respx.get(f"{API_URL}/tracks/{TRACK_A}").mock(
        return_value=httpx.Response(
            200,
            json=track(
                id=TRACK_B,
                linked_from={"id": TRACK_A},
                external_urls={"spotify": "https://untrusted.example/track"},
            ),
        )
    )
    path = f"{PATH}/{snapshot['id']}/albums/{ALBUM_A}"
    details = client.get(path)
    assert details.status_code == 200
    assert details.json()["representativeTrack"]["id"] == TRACK_B
    assert (
        details.json()["representativeTrack"]["spotifyUrl"]
        == f"https://open.spotify.com/track/{TRACK_B}"
    )
    assert details.json()["trackDetailsUnavailable"] is False
    song.mock(
        return_value=httpx.Response(
            200, json=track(id=TRACK_B, linked_from={"id": ALBUM_C})
        )
    )
    spotify_cache.monthly_metadata.clear()
    assert client.get(path).json()["trackDetailsUnavailable"] is True

    async def saved_provenance():
        async with factory() as db, db.begin():
            profile = await profiles.get_by_user_id(db, user_id)
            record = await monthly_mosaics.get_for_month(
                db, profile.id, date(2026, 10, 1)
            )
            assert record.representative_track_ids == {ALBUM_A: TRACK_A}

    asyncio.run(saved_provenance())


@respx.mock
def test_same_album_tiles_save_distinct_songs_and_resolve_requested_song(monthly_owner):
    client, factory, user_id = monthly_owner
    refresh = mock_refresh()
    top = mock_top(
        [track(id=TRACK_A, name="First song"), track(id=TRACK_B, name="Second song")]
    )
    generated = client.post(PATH, json={})
    assert generated.status_code == 201
    snapshot = saved_snapshot(generated)
    tiles = snapshot["tiles"]
    assert [tile["spotifyTrackId"] for tile in tiles[:4]] == [
        TRACK_A,
        TRACK_B,
        TRACK_A,
        TRACK_B,
    ]
    assert {tile["spotifyAlbumId"] for tile in tiles} == {ALBUM_A}
    assert client.get(PATH).json()["items"] == [snapshot]
    repeated = client.post(PATH, json={})
    assert repeated.status_code == 200 and saved_snapshot(repeated) == snapshot
    assert refresh.call_count == top.call_count == 1

    spotify_cache.monthly_metadata.clear()
    album = respx.get(f"{API_URL}/albums/{ALBUM_A}").mock(
        return_value=httpx.Response(200, json=raw_album())
    )
    first = respx.get(f"{API_URL}/tracks/{TRACK_A}").mock(
        return_value=httpx.Response(200, json=track(id=TRACK_A, name="First song"))
    )
    second = respx.get(f"{API_URL}/tracks/{TRACK_B}").mock(
        return_value=httpx.Response(200, json=track(id=TRACK_B, name="Second song"))
    )
    path = f"{PATH}/{snapshot['id']}/albums/{ALBUM_A}"
    for track_id, title in [(TRACK_A, "First song"), (TRACK_B, "Second song")]:
        result = client.get(path, params={"track_id": track_id})
        assert result.status_code == 200
        assert result.json()["representativeTrack"]["id"] == track_id
        assert result.json()["representativeTrack"]["name"] == title
        assert (
            result.json()["representativeTrack"]["spotifyUrl"]
            == f"https://open.spotify.com/track/{track_id}"
        )
    assert first.call_count == second.call_count == 1
    calls_before = refresh.call_count
    assert client.get(path, params={"track_id": ALBUM_C}).status_code == 404
    assert client.get(path, params={"track_id": "bad"}).status_code == 422
    assert refresh.call_count == calls_before and album.call_count == 0
    second.mock(
        return_value=httpx.Response(200, json=track(id=TRACK_A, name="First song"))
    )
    spotify_cache.monthly_metadata.clear()
    unavailable = client.get(path, params={"track_id": TRACK_B})
    assert unavailable.status_code == 200
    assert unavailable.json()["representativeTrack"] is None
    assert unavailable.json()["trackDetailsUnavailable"] is True
    # A failed tile song never silently substitutes the album's representative.
    assert first.call_count == 1

    async def saved():
        async with factory() as db, db.begin():
            profile = await profiles.get_by_user_id(db, user_id)
            record = await monthly_mosaics.get_for_month(
                db, profile.id, date(2026, 10, 1)
            )
            assert record.tiles == tiles
            assert record.representative_track_ids == {ALBUM_A: TRACK_A}

    asyncio.run(saved())


@respx.mock
def test_track_query_must_match_same_album_tile_and_owner(monthly_owner):
    client, factory, _ = monthly_owner
    refresh = mock_refresh()
    mock_top([track(ALBUM_A, id=TRACK_A), track(ALBUM_B, id=TRACK_B)])
    snapshot = client.post(PATH, json={}).json()
    path = f"{PATH}/{snapshot['id']}/albums/{ALBUM_A}"
    assert client.get(path, params={"track_id": TRACK_B}).status_code == 404
    assert refresh.call_count == 1
    create_owner(
        factory,
        account_id=uuid4().hex,
        username=f"tile_visitor_{uuid4().hex[:8]}",
        token="tile-song-visitor",
    )
    client.cookies.set("mosaic_session", "tile-song-visitor")
    assert client.get(path, params={"track_id": TRACK_A}).status_code == 404
    client.cookies.clear()
    assert client.get(path, params={"track_id": TRACK_A}).status_code == 401
    assert refresh.call_count == 1


@respx.mock
def test_more_tiles_than_top_tracks_repeat_saved_songs_without_inventing_associations(
    monthly_owner,
):
    client, _, _ = monthly_owner
    mock_refresh()
    track_ids = [f"{index:022d}" for index in range(50)]
    top = mock_top([track(id=track_id) for track_id in track_ids])
    response = client.post(PATH, json={})
    assert response.status_code == 201
    tiles = response.json()["tiles"]
    assert len(tiles) > 50
    assert [tile["spotifyTrackId"] for tile in tiles[:50]] == track_ids
    assert [tile["spotifyTrackId"] for tile in tiles[50:]] == track_ids[
        : len(tiles) - 50
    ]
    assert {tile["spotifyAlbumId"] for tile in tiles} == {ALBUM_A}
    assert top.call_count == 1


@respx.mock
def test_older_representative_snapshot_keeps_fallback_without_tile_associations(
    monthly_owner,
):
    client, factory, user_id = monthly_owner

    async def old_snapshot():
        async with factory() as db, db.begin():
            profile = await profiles.get_by_user_id(db, user_id)
            record = await monthly_mosaics.create(
                db,
                profile.id,
                month=date(2026, 10, 1),
                generated_at=datetime(2026, 10, 1, tzinfo=UTC),
                source_track_count=2,
                album_ids=[ALBUM_A],
                layout=expand_preset("heart", [ALBUM_A]),
                representative_track_ids={ALBUM_A: TRACK_A},
            )
            return record.id

    snapshot_id = asyncio.run(old_snapshot())
    archive = client.get(PATH).json()["items"][0]
    assert all(tile["spotifyTrackId"] is None for tile in archive["tiles"])
    assert saved_snapshot(client.post(PATH, json={})) == archive
    path = f"{PATH}/{snapshot_id}/albums/{ALBUM_A}"
    # The stored album representative is a fallback, not invented per-tile history.
    assert client.get(path, params={"track_id": TRACK_A}).status_code == 404
    mock_refresh()
    respx.get(f"{API_URL}/albums/{ALBUM_A}").mock(
        return_value=httpx.Response(200, json=raw_album())
    )
    respx.get(f"{API_URL}/tracks/{TRACK_A}").mock(
        return_value=httpx.Response(200, json=track())
    )
    details = client.get(path)
    assert details.status_code == 200
    assert details.json()["representativeTrack"]["id"] == TRACK_A
