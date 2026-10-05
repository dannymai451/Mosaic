"""Phase 3 privacy, anonymous sharing, and owner-only writes."""

from test_profile_update_api import create_owner


def test_public_profile_requires_saved_public_visibility(database_client):
    client, factory = database_client
    create_owner(factory, account_id="sharing-owner", username="share_owner", token="share-cookie")
    path = "/api/profiles/share_owner/public"
    private = client.get(path)
    missing = client.get("/api/profiles/no_such_profile/public")
    assert private.status_code == missing.status_code == 404
    assert private.json() == missing.json() == {"detail": "Profile not found"}
    assert private.headers["cache-control"] == "no-store"

    client.cookies.set("mosaic_session", "share-cookie")
    # Even the owner must use the owner endpoint to read a private profile.
    assert client.get(path).status_code == 404
    saved = client.patch("/api/me/profile", json={
        "display_name": "Shared Name",
        "bio": "Public music bio",
        "visibility": "public",
        "theme": {"preset": "paper"},
    })
    assert saved.status_code == 200
    client.cookies.clear()
    public = client.get(path)
    assert public.status_code == 200
    assert public.headers["cache-control"] == "no-store"
    assert public.json() == {
        "username": "share_owner",
        "displayName": "Shared Name",
        "images": [],
        "bio": "Public music bio",
        "theme": {"preset": "paper"},
    }
    assert client.get("/api/me").status_code == 401

    client.cookies.set("mosaic_session", "share-cookie")
    assert client.patch("/api/me/profile", json={"username": "renamed_owner"}).status_code == 200
    assert client.get(path).status_code == 404
    new_path = "/api/profiles/renamed_owner/public"
    assert client.get(new_path).status_code == 200
    assert client.patch("/api/me/profile", json={"visibility": "private"}).status_code == 200
    client.cookies.clear()
    assert client.get(new_path).status_code == 404


def test_visitors_and_other_owners_cannot_write_shared_profile(database_client):
    client, factory = database_client
    create_owner(factory, account_id="protected-owner", username="protected_owner", token="protected-cookie")
    create_owner(factory, account_id="visitor-owner", username="visitor_owner", token="visitor-cookie")
    client.cookies.set("mosaic_session", "protected-cookie")
    assert client.patch("/api/me/profile", json={"visibility": "public"}).status_code == 200
    path = "/api/profiles/protected_owner/public"
    original = client.get(path).json()

    for token in (None, "visitor-cookie", "unknown-session"):
        client.cookies.clear()
        if token:
            client.cookies.set("mosaic_session", token)
        for method in ("patch", "put", "post", "delete"):
            assert client.request(method, path, json={"bio": "Overwrite"}).status_code == 405
        forged = client.patch("/api/me/profile", json={
            "username": "protected_owner", "user_id": "protected-owner", "bio": "Overwrite",
        })
        assert forged.status_code in (401, 422)
        assert client.get(path).json() == original

    client.cookies.set("mosaic_session", "visitor-cookie")
    assert client.patch("/api/me/profile", json={"username": "protected_owner", "bio": "Overwrite"}).status_code == 409
    # A normal update by a different owner affects only that owner's profile.
    assert client.patch("/api/me/profile", json={"bio": "My own edit"}).status_code == 200
    assert client.get(path).json() == original
