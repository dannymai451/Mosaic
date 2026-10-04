import os

import httpx
import respx
from fastapi.testclient import TestClient

# Allows tests to run without a developer's real .env credentials.
os.environ.setdefault("SPOTIFY_CLIENT_ID", "test-client-id")
os.environ.setdefault("SPOTIFY_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault(
    "SPOTIFY_REDIRECT_URI",
    "http://127.0.0.1:8000/api/auth/spotify/callback",
)
os.environ.setdefault(
    "FRONTEND_URL",
    "http://127.0.0.1:3000",
)


from app.api.routes.auth import (
    SPOTIFY_ME_URL,
    SPOTIFY_TOKEN_URL,
)
from app.main import app

client = TestClient(app)


def test_callback_rejects_invalid_state():
    client.cookies.set(
        "spotify_oauth_state",
        "expected-state",
    )

    response = client.get(
        "/api/auth/spotify/callback",
        params={
            "code": "fake-code",
            "state": "wrong-state",
        },
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert (
        response.headers["location"]
        == "http://127.0.0.1:3000/connect?error=state_mismatch"
    )


@respx.mock
def test_callback_creates_session_and_returns_profile(database_client):
    client, _ = database_client
    respx.post(SPOTIFY_TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "fake-access-token",
                "token_type": "Bearer",
                "scope": "user-read-private",
                "expires_in": 3600,
                "refresh_token": "fake-refresh-token",
            },
        )
    )

    respx.get(SPOTIFY_ME_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "account_id": "test-account-id",
                "display_name": "Test User",
                "images": [
                    {
                        "url": "https://example.com/avatar.jpg",
                        "height": 300,
                        "width": 300,
                    }
                ],
            },
        )
    )

    client.cookies.set(
        "spotify_oauth_state",
        "expected-state",
    )

    response = client.get(
        "/api/auth/spotify/callback",
        params={
            "code": "valid-code",
            "state": "expected-state",
        },
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "http://127.0.0.1:3000/dashboard"

    assert client.cookies.get("mosaic_session") is not None

    me_response = client.get("/api/me")

    assert me_response.status_code == 200

    body = me_response.json()

    assert body["displayName"] == "Test User"
    assert body["images"][0]["url"] == "https://example.com/avatar.jpg"

    # Tokens must never be exposed through /api/me.
    assert "access_token" not in body
    assert "refresh_token" not in body
