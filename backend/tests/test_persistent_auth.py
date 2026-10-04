"""OAuth through HTTP, PostgreSQL persistence, restart, expiry, and logout."""

import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import respx
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from app.api.routes.auth import SPOTIFY_ME_URL, SPOTIFY_TOKEN_URL
from app.core.config import settings
from app.models import Profile, Session, SpotifyConnection, User
from app.repositories.sessions import token_digest


def login(client):
    start = client.get("/api/auth/spotify/start", follow_redirects=False)
    assert start.status_code == 307
    state = client.cookies.get("spotify_oauth_state")
    response = client.get(
        "/api/auth/spotify/callback",
        params={"code": "mock-code", "state": state},
        follow_redirects=False,
    )
    assert client.cookies.get("spotify_oauth_state") is None
    return response


@respx.mock
def test_repeat_login_restart_expiry_and_logout(database_client, migrated_database_url):
    client, factory = database_client
    account_id = f"test-{uuid4().hex}"
    token_route = respx.post(SPOTIFY_TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "mock-access",
                "refresh_token": "mock-refresh",
                "scope": "user-read-private",
            },
        )
    )
    respx.get(SPOTIFY_ME_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "account_id": account_id,
                "display_name": "Persistent User",
                "images": [{"url": "https://example.com/avatar.jpg"}],
            },
        )
    )
    assert login(client).headers["location"].endswith("/dashboard")
    first_cookie = client.cookies.get("mosaic_session")

    async def inspect_first():
        async with factory() as db, db.begin():
            user = await db.scalar(
                select(User).where(User.spotify_account_id == account_id)
            )
            profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
            connection = await db.get(SpotifyConnection, user.id)
            assert connection.encrypted_refresh_token != "mock-refresh"
            assert (
                Fernet(settings.token_encryption_key).decrypt(
                    connection.encrypted_refresh_token.encode()
                )
                == b"mock-refresh"
            )
            assert await db.get(Session, first_cookie) is None
            assert (
                await db.get(Session, token_digest(first_cookie))
            ).user_id == user.id
            profile.bio = "Preserve my edits"
            profile.display_name = "Edited name"
            return user.id, profile.id

    user_id, profile_id = asyncio.run(inspect_first())
    # Spotify may omit a refresh token on a later authorization.
    token_route.mock(
        return_value=httpx.Response(200, json={"access_token": "mock-access"})
    )
    assert login(client).headers["location"].endswith("/dashboard")
    cookie = client.cookies.get("mosaic_session")
    assert cookie != first_cookie

    async def inspect_repeat():
        async with factory() as db:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(User.spotify_account_id == account_id)
                )
                == 1
            )
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(Profile)
                    .where(Profile.user_id == user_id)
                )
                == 1
            )
            assert (await db.get(Profile, profile_id)).bio == "Preserve my edits"
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(SpotifyConnection)
                    .where(SpotifyConnection.user_id == user_id)
                )
                == 1
            )

    asyncio.run(inspect_repeat())
    expected = {
        "displayName": "Edited name",
        "images": [{"url": "https://example.com/avatar.jpg"}],
    }
    assert client.get("/api/me").json() == expected
    # A new interpreter has no in-memory auth state or shared database engine.
    code = """import json, sys
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    client.cookies.set("mosaic_session", sys.argv[1])
    response = client.get("/api/me")
    assert response.status_code == 200
    print(json.dumps(response.json()))
"""
    restarted = subprocess.run(
        [sys.executable, "-c", code, cookie],
        env={**os.environ, "DATABASE_URL": migrated_database_url},
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(restarted.stdout) == expected
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set("mosaic_session", cookie)
    assert client.get("/api/me").status_code == 401

    async def expire():
        async with factory() as db, db.begin():
            assert await db.get(Session, token_digest(cookie)) is None
            session = await db.get(Session, token_digest(first_cookie))
            session.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    asyncio.run(expire())
    client.cookies.set("mosaic_session", first_cookie)
    assert client.get("/api/me").status_code == 401
    client.cookies.set("mosaic_session", "unknown")
    assert client.get("/api/me").status_code == 401


@respx.mock
def test_missing_refresh_token_rolls_back_account(database_client):
    client, factory = database_client
    account_id = f"rollback-{uuid4().hex}"
    respx.post(SPOTIFY_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "mock"})
    )
    respx.get(SPOTIFY_ME_URL).mock(
        return_value=httpx.Response(200, json={"account_id": account_id})
    )
    assert login(client).headers["location"].endswith("error=missing_refresh_token")
    assert client.cookies.get("mosaic_session") is None

    async def inspect():
        async with factory() as db:
            assert (
                await db.scalar(
                    select(User).where(User.spotify_account_id == account_id)
                )
                is None
            )

    asyncio.run(inspect())
