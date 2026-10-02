import base64
import hashlib
import secrets

import httpx
from fastapi import APIRouter, Cookie, HTTPException, Response
from fastapi.responses import RedirectResponse

from app.core.config import settings


router = APIRouter(prefix="/api/auth/spotify", tags=["spotify-auth"])

me_router = APIRouter(tags=["me"])


SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_ME_URL = "https://api.spotify.com/v1/me"

SCOPES = ["user-read-private"]


# Temporary Phase 1 storage.
# PostgreSQL-backed sessions come later.
sessions: dict[str, dict] = {}


@router.get("/start")
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
    )

    return response


@router.get("/callback")
async def spotify_callback(
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    spotify_oauth_state: str | None = Cookie(default=None),
):
    if error:
        return RedirectResponse(
            f"{settings.frontend_url}/connect?error={error}"
        )

    if not code or not state or not spotify_oauth_state:
        raise HTTPException(
            status_code=400,
            detail="Missing OAuth callback parameters.",
        )

    if not secrets.compare_digest(state, spotify_oauth_state):
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state.",
        )

    credentials = (
        f"{settings.spotify_client_id}:{settings.spotify_client_secret}"
    )

    basic_auth = base64.b64encode(
        credentials.encode()
    ).decode()

    async with httpx.AsyncClient(timeout=10.0) as client:
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

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Spotify token exchange failed.",
            )

        token_data = token_response.json()
        access_token = token_data["access_token"]

        profile_response = await client.get(
            SPOTIFY_ME_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        if profile_response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Could not retrieve Spotify profile.",
            )

        profile = profile_response.json()

    session_id = secrets.token_urlsafe(32)

    sessions[session_id] = {
        "spotify_account_id": profile.get("account_id"),
        "display_name": profile.get("display_name"),
        "images": profile.get("images", []),

        # Server-side only.
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
    }

    redirect = RedirectResponse(
        f"{settings.frontend_url}/dashboard"
    )

    redirect.delete_cookie("spotify_oauth_state")

    redirect.set_cookie(
        key="mosaic_session",
        value=session_id,
        httponly=True,
        secure=False,  # True once deployed behind HTTPS
        samesite="lax",
        max_age=60 * 60,
    )

    return redirect

@me_router.get("/me")
async def get_current_user(
    mosaic_session: str | None = Cookie(default=None),
):
    if not mosaic_session:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated.",
        )

    session = sessions.get(mosaic_session)

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Session expired.",
        )

    return {
        "spotifyAccountId": session["spotify_account_id"],
        "displayName": session["display_name"],
        "images": session["images"],
    }