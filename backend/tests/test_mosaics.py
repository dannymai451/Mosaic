"""Phase 5 presets, atomic layout saves, ownership, and public privacy."""

import asyncio
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from test_albums import ALBUM_A, ALBUM_B, mock_refresh, owner, raw_album
from test_profile_update_api import create_owner

from app.models import Mosaic, Profile
from app.repositories import mosaics, profiles
from app.schemas.mosaic import MosaicLayout
from app.services.mosaic import PRESETS, expand_preset
from app.services.spotify import API_URL

__all__ = ["owner"]  # Expose the shared pytest fixture in this test module.


def tile(album_id=ALBUM_A, x=0, y=0):
    return {"spotifyAlbumId": album_id, "x": x, "y": y}


def layout(tiles=None, **changes):
    return {
        "preset_key": "blank",
        "grid_width": 9,
        "grid_height": 9,
        "tiles": tiles or [],
        **changes,
    }


def feature(factory, user_id, album_ids=None):
    async def prepare():
        async with factory() as db, db.begin():
            profile = await profiles.get_by_user_id(db, user_id)
            await profiles.set_featured_albums(
                db, profile, album_ids or [ALBUM_A, ALBUM_B]
            )
            return profile.username

    return asyncio.run(prepare())


def create(client, preset="blank"):
    response = client.post("/api/me/mosaics", json={"preset_key": preset})
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize("key", ["heart", "star", "music-note", "blank"])
def test_presets_expand_to_unique_bounded_coordinates(key):
    preset = next(item for item in PRESETS if item.key == key)
    expanded = expand_preset(key, [ALBUM_A, ALBUM_B])
    assert [(tile.x, tile.y) for tile in expanded.tiles] == [
        (point.x, point.y) for point in preset.coordinates
    ]
    assert len({(tile.x, tile.y) for tile in expanded.tiles}) == len(expanded.tiles)
    assert all(0 <= tile.x < 9 and 0 <= tile.y < 9 for tile in expanded.tiles)
    assert [tile.spotifyAlbumId for tile in expanded.tiles] == [
        [ALBUM_A, ALBUM_B][i % 2] for i in range(len(expanded.tiles))
    ]
    assert bool(expanded.tiles) is (key != "blank")
    assert expand_preset(key, []).tiles == []
    if key != "blank":
        assert all(
            item.spotifyAlbumId == ALBUM_A
            for item in expand_preset(key, [ALBUM_A]).tiles
        )


@pytest.mark.parametrize(
    "body",
    [
        layout([tile(), tile(ALBUM_B)]),
        layout([tile(x=9)]),
        layout([tile(y=9)]),
        layout([tile(x=-1)]),
        layout([tile(x=True)]),
        layout([tile(x=0.5)]),
        layout([tile("invalid")]),
        layout([tile(x=1)], grid_width=1),
        layout(grid_width=0),
        layout(grid_height=13),
        layout(preset_key="unknown"),
        layout(
            tiles=[tile(x=i % 12, y=i // 12) for i in range(101)],
            grid_width=12,
            grid_height=12,
        ),
        layout(user_id=str(uuid4())),
        {**layout(), "tiles": None},
    ],
)
def test_layout_validation(body):
    with pytest.raises(ValidationError):
        MosaicLayout.model_validate(body)


def test_create_save_reload_and_activate_exact_layout(owner):
    client, factory, user_id = owner
    username = feature(factory, user_id)
    assert client.get("/api/me/mosaics").json() == []
    presets = client.get("/api/me/mosaic-presets").json()
    assert {preset["key"] for preset in presets} == {
        "heart",
        "star",
        "music-note",
        "blank",
    }
    created = create(client, "heart")
    assert (
        created["tiles"]
        == expand_preset("heart", [ALBUM_A, ALBUM_B]).model_dump()["tiles"]
    )
    assert not created["is_active"]
    assert client.post("/api/me/mosaics", json={}).status_code == 409
    path = f"/api/me/mosaics/{created['id']}"
    body = layout(
        [tile(ALBUM_B, x=6, y=1), tile(x=0, y=5), tile(x=2, y=3)],
        grid_width=7,
        grid_height=6,
    )
    response = client.put(path, json=body)
    assert response.status_code == 200
    assert {key: response.json()[key] for key in body} == body
    assert client.get("/api/me/mosaics").json() == [response.json()]
    assert response.headers["cache-control"] == "no-store"
    assert (
        client.patch("/api/me/profile", json={"visibility": "public"}).status_code
        == 200
    )
    public_path = f"/api/profiles/{username}/public"
    assert client.get(public_path).json()["mosaic"] is None
    active = client.post(f"{path}/activate")
    assert active.status_code == 200 and active.json()["is_active"]
    assert client.post(f"{path}/activate").json() == active.json()
    client.cookies.clear()
    public = client.get(public_path)
    assert public.status_code == 200 and public.json()["mosaic"] == body
    assert set(public.json()["mosaic"]) == {
        "preset_key",
        "grid_width",
        "grid_height",
        "tiles",
    }
    assert "profile_id" not in public.text and "user_id" not in public.text


def test_invalid_or_unfeatured_layout_never_replaces_save(owner):
    client, factory, user_id = owner
    feature(factory, user_id, [ALBUM_A])
    original = create(client, "star")
    path = f"/api/me/mosaics/{original['id']}"
    for body in [
        layout([tile(ALBUM_B)]),
        layout([tile(), tile()]),
        layout([tile(x=9)]),
    ]:
        assert client.put(path, json=body).status_code == 422
        assert client.get("/api/me/mosaics").json() == [original]
    # Complete replacement removes old tiles; empty layouts need no Spotify call.
    assert client.put(path, json=layout()).json()["tiles"] == []


def test_owner_isolation_and_invalid_sessions(owner):
    client, factory, user_id = owner
    feature(factory, user_id)
    original = create(client)
    path = f"/api/me/mosaics/{original['id']}"
    create_owner(
        factory,
        account_id=uuid4().hex,
        username=f"visitor_{uuid4().hex[:12]}",
        token="mosaic-visitor",
    )
    for token in [None, "unknown-mosaic-cookie", "mosaic-visitor"]:
        client.cookies.clear()
        if token:
            client.cookies.set("mosaic_session", token)
        expected = 404 if token == "mosaic-visitor" else 401
        assert client.put(path, json=layout()).status_code == expected
        assert client.post(f"{path}/activate").status_code == expected
        if token != "mosaic-visitor":
            assert client.get("/api/me/mosaics").status_code == 401
            assert client.post("/api/me/mosaics", json={}).status_code == 401
        else:
            assert client.get("/api/me/mosaics").json() == []
    forged = client.post("/api/me/mosaics", json={"user_id": str(user_id)})
    assert forged.status_code == 422
    assert client.put(f"/api/me/mosaics/{uuid4()}", json=layout()).status_code == 404


@respx.mock
def test_public_details_require_public_active_tile_and_never_leak_tokens(owner):
    client, factory, user_id = owner
    username = feature(factory, user_id, [ALBUM_A])
    created = create(client, "music-note")
    path = f"/api/me/mosaics/{created['id']}"
    album_path = f"/api/profiles/{username}/albums/{ALBUM_A}"
    assert client.get(album_path).status_code == 404
    assert client.post(f"{path}/activate").status_code == 200
    assert client.get(album_path).status_code == 404
    assert (
        client.patch("/api/me/profile", json={"visibility": "public"}).status_code
        == 200
    )
    client.cookies.clear()
    refresh = mock_refresh(refresh_token="rotated-public-refresh")
    album = respx.get(f"{API_URL}/albums/{ALBUM_A}").mock(
        return_value=httpx.Response(200, json=raw_album())
    )
    result = client.get(album_path)
    assert result.status_code == 200 and result.json()["name"] == "Test album"
    assert result.headers["cache-control"] == "no-store"
    assert "server-access" not in result.text and "refresh" not in result.text
    assert client.get(f"/api/profiles/{username}/albums/{ALBUM_B}").status_code == 404
    assert client.get(f"/api/profiles/missing_profile/albums/{ALBUM_A}").json() == {
        "detail": "Album not found"
    }
    for method in ["put", "patch", "post", "delete"]:
        assert client.request(method, album_path, json={}).status_code == 405
    album.mock(
        return_value=httpx.Response(
            429, headers={"Retry-After": "7"}, json={"secret": "hidden"}
        )
    )
    rate_limit = client.get(album_path)
    assert rate_limit.status_code == 429 and rate_limit.headers["retry-after"] == "7"
    assert rate_limit.json() == {"detail": "spotify_rate_limited"}
    # Public layout/profile reads have no Spotify dependency, including during outages.
    assert client.get(f"/api/profiles/{username}/public").status_code == 200
    album.mock(return_value=httpx.Response(404))
    assert client.get(album_path).json() == {"detail": "spotify_album_unavailable"}
    calls_before_private = refresh.call_count
    client.cookies.set("mosaic_session", "mosaic-visitor-invalid")

    # Withdraw visibility directly, without depending on a visitor session.
    async def withdraw():
        async with factory() as db, db.begin():
            profile = await profiles.get_by_user_id(db, user_id)
            await profiles.update(db, profile, visibility="private")

    asyncio.run(withdraw())
    assert client.get(album_path).status_code == 404
    assert client.get(f"/api/profiles/{username}/public").status_code == 404
    assert refresh.call_count == calls_before_private


def test_featured_removal_prunes_active_layout_atomically(owner, monkeypatch):
    client, factory, user_id = owner
    feature(factory, user_id)
    original = create(client, "heart")
    assert client.post(f"/api/me/mosaics/{original['id']}/activate").status_code == 200
    real_prune = mosaics.retain_featured_albums

    async def fail(db, mosaic, album_ids):
        await real_prune(db, mosaic, album_ids)
        raise RuntimeError("Simulated failure after both flushes")

    monkeypatch.setattr(mosaics, "retain_featured_albums", fail)
    with pytest.raises(RuntimeError, match="Simulated failure"):
        client.put("/api/me/featured-albums", json={"album_ids": [ALBUM_A]})
    assert client.get("/api/me/featured-albums").json()["albumIds"] == [
        ALBUM_A,
        ALBUM_B,
    ]
    assert client.get("/api/me/mosaics").json()[0]["tiles"] == original["tiles"]
    monkeypatch.setattr(mosaics, "retain_featured_albums", real_prune)
    assert (
        client.put("/api/me/featured-albums", json={"album_ids": [ALBUM_A]}).status_code
        == 200
    )
    result = client.get("/api/me/mosaics").json()[0]
    assert result["is_active"]
    assert result["tiles"] == [
        item for item in original["tiles"] if item["spotifyAlbumId"] == ALBUM_A
    ]


def test_saved_layout_rollback_unique_profile_and_cascade(owner):
    client, factory, user_id = owner
    feature(factory, user_id)
    original = create(client, "star")

    async def scenario():
        async with factory() as db:
            with pytest.raises(RuntimeError):
                async with db.begin():
                    profile = await profiles.get_by_user_id(db, user_id)
                    mosaic = await mosaics.get_by_profile_id(db, profile.id)
                    await mosaics.save(
                        db, mosaic, MosaicLayout.model_validate(layout([tile()]))
                    )
                    raise RuntimeError("rollback")
            with pytest.raises(IntegrityError):
                async with db.begin():
                    profile = await profiles.get_by_user_id(db, user_id)
                    await mosaics.create(db, profile.id, expand_preset("blank", []))

    asyncio.run(scenario())
    assert client.get("/api/me/mosaics").json() == [original]

    async def remove_profile():
        async with factory() as db, db.begin():
            await db.execute(delete(Profile).where(Profile.user_id == user_id))
            assert await db.get(Mosaic, UUID(original["id"])) is None

    asyncio.run(remove_profile())
