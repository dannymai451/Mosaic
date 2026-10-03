import base64
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Response
from fastapi.responses import RedirectResponse

from app.core.config import settings


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

# Phase 1 only.
# Replaced by persistent database-backed sessions in Phase 2.
sessions: dict[str, dict] = {}


def redirect_to_connect(error: str) -> RedirectResponse:
    query = urlencode({"error": error})

    response = RedirectResponse(
        f"{settings.frontend_url}/connect?{query}"
    )

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

    credentials = (
        f"{settings.spotify_client_id}:{settings.spotify_client_secret}"
    )

    basic_auth = base64.b64encode(
        credentials.encode()
    ).decode()

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

    session_id = secrets.token_urlsafe(32)

    sessions[session_id] = {
        "spotify_account_id": profile.get("account_id"),
        "display_name": profile.get("display_name"),
        "images": profile.get("images", []),

        # Never returned to the browser.
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
    }

    response = RedirectResponse(
        f"{settings.frontend_url}/dashboard"
    )

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
    mosaic_session: str | None = Cookie(default=None),
):
    if not mosaic_session:
        return Response(status_code=401)

    session = sessions.get(mosaic_session)

    if not session:
        return Response(status_code=401)

    # Deliberately minimal browser-facing DTO.
    return {
        "displayName": session["display_name"],
        "images": session["images"],
    }


@auth_router.post("/logout", status_code=204)
async def logout(
    mosaic_session: str | None = Cookie(default=None),
):
    if mosaic_session:
        sessions.pop(mosaic_session, None)

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
