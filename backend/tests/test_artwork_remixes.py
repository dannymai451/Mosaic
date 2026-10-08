"""Remix persistence, no new listening calls, and revocable anonymous access."""

from io import BytesIO
from uuid import uuid4

import httpx
import respx
from PIL import Image
from test_albums import mock_refresh, owner
from test_monthly_mosaics import (
    ALBUM_A,
    PATH,
    TRACK_A,
    TRACK_B,
    mock_top,
    monthly_owner,
    track,
)
from test_profile_update_api import create_owner

from app.services import spotify_cache
from app.services.spotify import API_URL

__all__ = ["monthly_owner", "owner"]


def generate(client):
    mock_refresh(expires_in=3600)
    mock_top([track(), track(id=TRACK_B)])
    result = client.post(PATH, json={})
    assert result.status_code == 201
    return result.json()


def create(client, snapshot, shape="ghost"):
    result = client.post(
        f"{PATH}/{snapshot['id']}/remixes",
        json={"name": "After dark", "style": {"shape": shape}},
    )
    assert result.status_code == 201
    return result.json()


@respx.mock
def test_all_shapes_preserve_songs_without_spotify_and_source_changes(monthly_owner):
    client, _, _ = monthly_owner
    snapshot = generate(client)
    archive = client.get(PATH).json()
    presets = client.get("/api/me/remix-shapes").json()["items"]
    assert {item["key"] for item in presets} == {"pumpkin", "ghost", "bat", "skull"}
    for preset in presets:
        remix = create(client, snapshot, preset["key"])
        assert remix["share_id"] is None
        tiles = remix["layout"]["tiles"]
        assert 50 <= len(tiles) <= 100
        assert len({(tile["x"], tile["y"]) for tile in tiles}) == len(tiles)
        assert all(0 <= tile["x"] < 12 and 0 <= tile["y"] < 12 for tile in tiles)
        assert {(tile["spotifyAlbumId"], tile["spotifyTrackId"]) for tile in tiles} == {
            (ALBUM_A, TRACK_A),
            (ALBUM_A, TRACK_B),
        }
    assert client.get(PATH).json() == archive
    assert len(respx.calls) == 2
    assert len(client.get(f"{PATH}/{snapshot['id']}/remixes").json()["items"]) == 4


@respx.mock
def test_shared_design_is_scoped_anonymous_and_revocable(monthly_owner):
    client, _, _ = monthly_owner
    snapshot = generate(client)
    remix = create(client, snapshot)
    owner_path = f"/api/me/remixes/{remix['id']}"
    token = client.post(f"{owner_path}/share").json()["share_id"]
    public = f"/api/artworks/{token}"
    cookie = client.cookies.get("mosaic_session")
    client.cookies.clear()
    result = client.get(public)
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    assert set(result.json()) == {
        "name",
        "month",
        "style",
        "layout",
        "background_url",
        "display_name",
    }
    assert "server-access" not in result.text and snapshot["id"] not in result.text
    assert (
        client.get(
            f"{public}/albums/{ALBUM_A}", params={"track_id": TRACK_A}
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"{public}/albums/{ALBUM_A}", params={"track_id": "9" * 22}
        ).status_code
        == 404
    )
    assert client.get(PATH).status_code == 401
    assert client.put(owner_path, json={}).status_code == 401
    assert len(respx.calls) == 2
    client.cookies.set("mosaic_session", cookie)
    assert client.delete(f"{owner_path}/share").status_code == 204
    assert client.get(public).status_code == 404
    assert client.get(f"{public}/background").status_code == 404
    assert (
        client.get(
            f"{public}/albums/{ALBUM_A}", params={"track_id": TRACK_A}
        ).status_code
        == 404
    )
    assert client.post(f"{owner_path}/share").json()["share_id"] != token


@respx.mock
def test_foreign_owner_cannot_read_edit_upload_or_share(monthly_owner):
    client, factory, _ = monthly_owner
    snapshot = generate(client)
    remix = create(client, snapshot)
    create_owner(
        factory,
        account_id=uuid4().hex,
        username=f"remix_{uuid4().hex[:8]}",
        token="remix-visitor",
    )
    client.cookies.set("mosaic_session", "remix-visitor")
    path = f"/api/me/remixes/{remix['id']}"
    assert client.get(f"{PATH}/{snapshot['id']}/remixes").status_code == 404
    assert client.post(f"{PATH}/{snapshot['id']}/remixes", json={}).status_code == 404
    for method, suffix, options in [
        ("PUT", "", {"json": {}}),
        ("DELETE", "", {}),
        ("POST", "/share", {}),
        ("DELETE", "/share", {}),
        ("PUT", "/background", {"content": b"image"}),
        ("GET", "/background", {}),
    ]:
        assert client.request(method, path + suffix, **options).status_code == 404


@respx.mock
def test_background_is_normalized_and_private_until_shared(monthly_owner):
    client, _, _ = monthly_owner
    remix = create(client, generate(client))
    path = f"/api/me/remixes/{remix['id']}"
    buffer = BytesIO()
    Image.new("RGBA", (1800, 900), (80, 60, 100, 150)).save(buffer, format="PNG")
    upload = client.put(f"{path}/background", content=buffer.getvalue())
    assert upload.status_code == 200
    photo = client.get(upload.json()["background_url"])
    assert photo.headers["content-type"] == "image/jpeg"
    with Image.open(BytesIO(photo.content)) as image:
        assert image.size == (1600, 800) and not image.getexif()
    assert (
        client.put(
            f"{path}/background", content=b'<svg onload="alert(1)"/>'
        ).status_code
        == 422
    )
    assert client.put(f"{path}/background", content=b"x" * 8_000_001).status_code == 413
    token = client.post(f"{path}/share").json()["share_id"]
    assert client.get(f"/api/artworks/{token}/background").content == photo.content
    assert client.delete(f"{path}/background").json()["background_url"] is None
    assert client.get(f"/api/artworks/{token}/background").status_code == 404


@respx.mock
def test_update_limits_validation_and_delete(monthly_owner):
    client, _, _ = monthly_owner
    snapshot = generate(client)
    remix = create(client, snapshot)
    path = f"/api/me/remixes/{remix['id']}"
    changed = client.put(
        path,
        json={
            "name": "Ghost notes",
            "style": {
                "shape": "bat",
                "frame_style": "double",
                "frame_width": 12,
                "background_color": "#abcdef",
            },
        },
    )
    assert changed.status_code == 200
    assert changed.json()["layout"]["preset_key"] == "bat"
    for bad in [
        {"style": {"background_color": "url(evil)"}},
        {"style": {"shape": "unknown"}},
        {"style": {"frame_width": 99}},
        {"tiles": []},
    ]:
        assert client.put(path, json=bad).status_code == 422
    for _ in range(11):
        create(client, snapshot)
    assert client.post(f"{PATH}/{snapshot['id']}/remixes", json={}).status_code == 409
    assert client.delete(path).status_code == 204
    assert len(client.get(f"{PATH}/{snapshot['id']}/remixes").json()["items"]) == 11
    assert len(respx.calls) == 2


@respx.mock
def test_public_cache_miss_uses_saved_song_and_propagates_rate_limit(monthly_owner):
    client, _, _ = monthly_owner
    remix = create(client, generate(client))
    token = client.post(f"/api/me/remixes/{remix['id']}/share").json()["share_id"]
    spotify_cache.monthly_metadata.clear()
    song = respx.get(f"{API_URL}/tracks/{TRACK_A}").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "10514"})
    )
    response = client.get(
        f"/api/artworks/{token}/albums/{ALBUM_A}", params={"track_id": TRACK_A}
    )
    assert response.status_code == 429 and response.headers["retry-after"] == "10514"
    assert song.call_count == 1 and len(respx.calls) == 3
