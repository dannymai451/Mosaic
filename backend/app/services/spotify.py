"""Server-only Spotify token refresh and normalized saved-library reads."""

import re

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import SpotifyConnection
from app.repositories import spotify_connections
from app.schemas.album import Album, AlbumPage

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"
LIBRARY_SCOPE = "user-library-read"


class SpotifyError(Exception):
    def __init__(self, status: int, code: str, retry_after: str | None = None):
        self.status = status
        self.code = code
        self.retry_after = retry_after
        super().__init__(code)


def response_json(response: httpx.Response):
    if response.status_code == 429:
        retry = response.headers.get("Retry-After", "")
        raise SpotifyError(
            429,
            "spotify_rate_limited",
            retry if retry.isascii() and retry.isdigit() else None,
        )
    if response.status_code in {401, 403}:
        raise SpotifyError(403, "spotify_reconnect_required")
    if response.status_code != 200:
        raise SpotifyError(502, "spotify_unavailable")
    try:
        return response.json()
    except ValueError as exc:
        raise SpotifyError(502, "spotify_invalid_response") from exc


def normalize_album(raw: dict) -> Album:
    try:
        album_id = raw["id"]
        if not isinstance(album_id, str) or not re.fullmatch(
            r"[a-zA-Z0-9]{22}", album_id
        ):
            raise ValueError("Invalid album ID")
        images = raw.get("images") or []
        image = images[0].get("url") if images else None
        return Album(
            id=album_id,
            name=raw.get("name") or "Unavailable album",
            artists=[artist["name"] for artist in raw.get("artists", [])],
            imageUrl=image
            if isinstance(image, str) and image.startswith("https://")
            else None,
            spotifyUrl=f"https://open.spotify.com/album/{album_id}",
            releaseDate=raw.get("release_date", ""),
            totalTracks=raw.get("total_tracks", 0),
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise SpotifyError(502, "spotify_invalid_response") from exc


class SpotifyClient:
    def __init__(
        self, client: httpx.AsyncClient, db: AsyncSession, connection: SpotifyConnection
    ):
        self.client = client
        self.db = db
        self.connection = connection
        self.access_token = ""

    async def refresh(self) -> None:
        # The caller owns the transaction, including rotated refresh-token writes.
        if not settings.token_encryption_key:
            raise SpotifyError(503, "spotify_not_configured")
        try:
            cipher = Fernet(settings.token_encryption_key)
            refresh_token = cipher.decrypt(
                self.connection.encrypted_refresh_token.encode()
            ).decode()
        except (InvalidToken, ValueError, UnicodeError) as exc:
            raise SpotifyError(403, "spotify_reconnect_required") from exc
        try:
            response = await self.client.post(
                TOKEN_URL,
                auth=httpx.BasicAuth(
                    settings.spotify_client_id, settings.spotify_client_secret
                ),
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            )
        except httpx.RequestError as exc:
            raise SpotifyError(502, "spotify_unavailable") from exc
        if response.status_code == 400:
            raise SpotifyError(403, "spotify_reconnect_required")
        data = response_json(response)
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("access_token"), str)
            or not data["access_token"]
        ):
            raise SpotifyError(502, "spotify_invalid_response")
        rotated = data.get("refresh_token")
        scopes = data.get("scope", self.connection.scopes)
        if (
            rotated is not None and (not isinstance(rotated, str) or not rotated)
        ) or not isinstance(scopes, str):
            raise SpotifyError(502, "spotify_invalid_response")
        self.connection = await spotify_connections.upsert(
            self.db,
            user_id=self.connection.user_id,
            encrypted_refresh_token=(
                cipher.encrypt(rotated.encode()).decode()
                if rotated
                else self.connection.encrypted_refresh_token
            ),
            scopes=scopes,
        )
        self.access_token = data["access_token"]

    async def get(self, path: str, params: dict | None = None):
        try:
            response = await self.client.get(
                f"{API_URL}{path}",
                params=params,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            if response.status_code == 401:
                # One bounded retry; persist rotation even if the retried read fails.
                async with self.db.begin():
                    self.connection = await spotify_connections.get_for_update(
                        self.db, self.connection.user_id
                    )
                    if self.connection is None:
                        raise SpotifyError(403, "spotify_reconnect_required")
                    await self.refresh()
                response = await self.client.get(
                    f"{API_URL}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )
        except httpx.RequestError as exc:
            raise SpotifyError(502, "spotify_unavailable") from exc
        return response_json(response)

    async def saved_albums(self, *, limit: int, offset: int) -> AlbumPage:
        data = await self.get("/me/albums", {"limit": limit, "offset": offset})
        try:
            raw_items = data["items"]
            total = data["total"]
            if (
                not isinstance(raw_items, list)
                or not isinstance(total, int)
                or total < 0
            ):
                raise ValueError("Invalid page")
            return AlbumPage(
                items=[
                    normalize_album(item["album"])
                    for item in raw_items
                    if item.get("album") is not None
                ],
                total=total,
                nextOffset=offset + limit if data.get("next") and raw_items else None,
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise SpotifyError(502, "spotify_invalid_response") from exc

    async def require_saved(self, album_ids: list[str]) -> None:
        # Spotify's replacement library endpoint takes at most 40 URIs.
        for start in range(0, len(album_ids), 40):
            batch = album_ids[start : start + 40]
            result = await self.get(
                "/me/library/contains",
                {"uris": ",".join(f"spotify:album:{album_id}" for album_id in batch)},
            )
            if (
                not isinstance(result, list)
                or len(result) != len(batch)
                or any(type(value) is not bool for value in result)
            ):
                raise SpotifyError(502, "spotify_invalid_response")
            if not all(result):
                raise SpotifyError(422, "album_not_saved")
