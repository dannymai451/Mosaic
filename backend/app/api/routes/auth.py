import base64
import secrets
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.repositories import profiles, sessions
from app.services.auth import persist_login

spotify_router = APIRouter(
    prefix="/api/auth/spotify",
    tags=["spotify-auth"],
)

auth_router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)

me_router = APIRouter(tags=["me"])


SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_ME_URL = "https://api.spotify.com/v1/me"

SCOPES = ["user-read-private"]


def redirect_to_connect(error: str) -> RedirectResponse:
    query = urlencode({"error": error})

    response = RedirectResponse(f"{settings.frontend_url}/connect?{query}")

    # Makes OAuth state effectively one-time use.
    response.delete_cookie("spotify_oauth_state", path="/")

    return response


@spotify_router.get("/start")
async def spotify_login():
    state = secrets.token_urlsafe(32)

    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
    }

    request = httpx.Request(
        "GET",
        SPOTIFY_AUTHORIZE_URL,
        params=params,
    )

    response = RedirectResponse(str(request.url))

    response.set_cookie(
        key="spotify_oauth_state",
        value=state,
        httponly=True,
        secure=False,  # True in production HTTPS
        samesite="lax",
        max_age=600,
        path="/",
    )

    return response


@spotify_router.get("/callback")
async def spotify_callback(
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    spotify_oauth_state: str | None = Cookie(default=None),
):
    # Spotify sends state back for both approval and denial.
    # Always validate it before processing the result.
    if not state or not spotify_oauth_state:
        return redirect_to_connect("missing_state")

    if not secrets.compare_digest(state, spotify_oauth_state):
        return redirect_to_connect("state_mismatch")

    if error:
        return redirect_to_connect(error)

    if not code:
        return redirect_to_connect("missing_code")

    credentials = f"{settings.spotify_client_id}:{settings.spotify_client_secret}"

    basic_auth = base64.b64encode(credentials.encode()).decode()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            token_response = await client.post(
                SPOTIFY_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.spotify_redirect_uri,
                },
                headers={
                    "Authorization": f"Basic {basic_auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
        except httpx.RequestError:
            return redirect_to_connect("spotify_unavailable")

        if token_response.status_code != 200:
            return redirect_to_connect("token_exchange_failed")

        token_data = token_response.json()

        access_token = token_data.get("access_token")

        if not access_token:
            return redirect_to_connect("token_exchange_failed")

        try:
            profile_response = await client.get(
                SPOTIFY_ME_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
            )
        except httpx.RequestError:
            return redirect_to_connect("spotify_unavailable")

        if profile_response.status_code == 401:
            return redirect_to_connect("spotify_unauthorized")

        if profile_response.status_code == 403:
            return redirect_to_connect("spotify_forbidden")

        if profile_response.status_code == 429:
            return redirect_to_connect("spotify_rate_limited")

        if profile_response.status_code != 200:
            return redirect_to_connect("spotify_profile_failed")

        profile = profile_response.json()

    try:
        session_id = await persist_login(db, profile, token_data)
    except ValueError as exc:
        return redirect_to_connect(
            str(exc)
            if str(exc)
            in {
                "spotify_profile_failed",
                "token_encryption_not_configured",
                "missing_refresh_token",
            }
            else "login_failed"
        )
    except SQLAlchemyError:
        return redirect_to_connect("login_failed")

    response = RedirectResponse(f"{settings.frontend_url}/dashboard")

    response.delete_cookie("spotify_oauth_state", path="/")

    response.set_cookie(
        key="mosaic_session",
        value=session_id,
        httponly=True,
        secure=False,  # True in production HTTPS
        samesite="lax",
        max_age=60 * 60,
        path="/",
    )

    return response


@me_router.get("/api/me")
async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    mosaic_session: str | None = Cookie(default=None),
):
    if not mosaic_session:
        return Response(status_code=401)

    session = await sessions.get_active(db, mosaic_session)

    if not session:
        return Response(status_code=401)

    profile = await profiles.get_by_user_id(db, session.user_id)
    if profile is None:
        return Response(status_code=401)

    # Deliberately minimal browser-facing DTO.
    return {
        "username": profile.username,
        "displayName": profile.display_name,
        "images": [{"url": profile.avatar_url}] if profile.avatar_url else [],
        "bio": profile.bio,
        "visibility": profile.visibility,
        "theme": profile.theme,
    }


@auth_router.post("/logout", status_code=204)
async def logout(
    db: Annotated[AsyncSession, Depends(get_db)],
    mosaic_session: str | None = Cookie(default=None),
):
    if mosaic_session:
        async with db.begin():
            await sessions.delete_by_token(db, mosaic_session)

    response = Response(status_code=204)

    response.delete_cookie(
        key="mosaic_session",
        path="/",
    )
    response.delete_cookie(
        key="mosaic_session",
        path="/api/auth/spotify",
    )

    return response
