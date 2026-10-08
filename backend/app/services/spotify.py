"""Server-only Spotify token refresh and normalized saved-library reads."""

import re

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import SpotifyConnection
from app.repositories import spotify_connections
from app.schemas.album import Album, AlbumPage
from app.schemas.monthly_mosaic import MonthlyAlbum, RepresentativeTrack
from app.services import spotify_cache

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"
LIBRARY_SCOPE = "user-library-read"
TOP_SCOPE = "user-top-read"


class SpotifyError(Exception):
    def __init__(self, status: int, code: str, retry_after: str | None = None):
        self.status = status
        self.code = code
        self.retry_after = retry_after
        super().__init__(code)


def response_json(response: httpx.Response):
    if response.status_code == 404:
        raise SpotifyError(404, "spotify_album_unavailable")
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


def normalize_representative_track(
    raw: dict, requested_id: str, album_id: str
) -> RepresentativeTrack:
    """Verify saved provenance, allowing Spotify's explicit track relinking."""
    try:
        track_id = raw["id"]
        if not isinstance(track_id, str) or not re.fullmatch(
            r"[a-zA-Z0-9]{22}", track_id
        ):
            raise ValueError("Invalid track ID")
        if (
            track_id != requested_id
            and raw.get("linked_from", {}).get("id") != requested_id
        ):
            raise ValueError("Track does not match saved provenance")
        if (
            raw["album"]["id"] != album_id
            or raw.get("is_local")
            or raw.get("is_playable") is False
        ):
            raise ValueError("Track is unavailable for this album")
        name = raw["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Invalid track name")
        return RepresentativeTrack(
            id=track_id,
            name=name,
            artists=[artist["name"] for artist in raw.get("artists", [])],
            spotifyUrl=f"https://open.spotify.com/track/{track_id}",
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
        self._token_deadline: float | None = None

    def use_cached_access_token(self) -> bool:
        token = spotify_cache.access_tokens.get(
            spotify_cache.connection_key(self.connection)
        )
        if token is None:
            return False
        self.access_token = token
        return True

    def cache_access_token(self) -> None:
        # Call only after the refresh-token transaction commits successfully.
        if self._token_deadline is not None:
            spotify_cache.access_tokens.put(
                spotify_cache.connection_key(self.connection),
                self.access_token,
                self._token_deadline,
            )
            self._token_deadline = None

    def invalidate_access_token(self) -> None:
        spotify_cache.access_tokens.discard(
            spotify_cache.connection_key(self.connection)
        )

    async def refresh(self) -> None:
        # The caller owns the transaction, including rotated refresh-token writes.
        self.invalidate_access_token()
        issued_at = spotify_cache.monotonic()
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
        self._token_deadline = spotify_cache.token_deadline(
            data.get("expires_in"), issued_at
        )

    async def get(self, path: str, params: dict | None = None):
        try:
            response = await self.client.get(
                f"{API_URL}{path}",
                params=params,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            if response.status_code == 401:
                # One bounded retry; persist rotation even if the retried read fails.
                rejected_token = self.access_token
                async with spotify_cache.serialized_refresh(self.connection.user_id):
                    async with self.db.begin():
                        self.connection = await spotify_connections.get_for_update(
                            self.db, self.connection.user_id
                        )
                        if self.connection is None:
                            raise SpotifyError(403, "spotify_reconnect_required")
                        if (
                            not self.use_cached_access_token()
                            or self.access_token == rejected_token
                        ):
                            await self.refresh()
                    self.cache_access_token()
                response = await self.client.get(
                    f"{API_URL}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )
        except httpx.RequestError as exc:
            raise SpotifyError(502, "spotify_unavailable") from exc
        if response.status_code in {401, 403}:
            self.invalidate_access_token()
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

    async def recent_top_albums(
        self,
    ) -> tuple[
        list[str], int, dict[str, str], dict[str, list[str]], dict[str, MonthlyAlbum]
    ]:
        # Short-term affinity reflects roughly four weeks, not exact play counts.
        data = await self.get(
            "/me/top/tracks", {"time_range": "short_term", "limit": 50, "offset": 0}
        )
        try:
            items = data["items"]
            if not isinstance(items, list) or len(items) > 50:
                raise ValueError("Invalid top tracks")
            counts: dict[str, int] = {}
            first_rank: dict[str, int] = {}
            representative_tracks: dict[str, str] = {}
            album_track_ids: dict[str, list[str]] = {}
            artwork: dict[str, MonthlyAlbum] = {}
            source_track_count = 0
            for rank, track in enumerate(items):
                if track is None:
                    continue
                if not isinstance(track, dict):
                    raise TypeError("Invalid track")
                if track.get("is_local") or track.get("is_playable") is False:
                    continue
                if track.get("album") is None:
                    continue
                track_id = track.get("id")
                if track_id is None:
                    continue
                if not isinstance(track_id, str) or not re.fullmatch(
                    r"[a-zA-Z0-9]{22}", track_id
                ):
                    raise ValueError("Invalid track ID")
                album = normalize_album(track["album"])
                try:
                    song = normalize_representative_track(track, track_id, album.id)
                    artwork[f"{album.id}:{track_id}"] = MonthlyAlbum(
                        **album.model_dump(), representativeTrack=song
                    )
                except SpotifyError:
                    # Keep valid listening IDs; missing display data can be retried.
                    pass
                counts[album.id] = counts.get(album.id, 0) + 1
                first_rank.setdefault(album.id, rank)
                representative_tracks.setdefault(album.id, track_id)
                album_tracks = album_track_ids.setdefault(album.id, [])
                if track_id not in album_tracks:
                    album_tracks.append(track_id)
                source_track_count += 1
            return (
                sorted(counts, key=lambda key: (-counts[key], first_rank[key])),
                source_track_count,
                representative_tracks,
                album_track_ids,
                artwork,
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise SpotifyError(502, "spotify_invalid_response") from exc

    async def monthly_album(self, album_id: str, track_id: str | None) -> MonthlyAlbum:
        """Resolve a previously authorized saved pair, never new listening."""
        if track_id:
            try:
                raw = await self.get(f"/tracks/{track_id}")
                song = normalize_representative_track(raw, track_id, album_id)
                album = normalize_album(raw["album"])
                result = MonthlyAlbum(**album.model_dump(), representativeTrack=song)
                spotify_cache.remember_metadata(self.connection, album_id, track_id, result)
                return result
            except SpotifyError as exc:
                if exc.status == 429:
                    raise
        album = normalize_album(await self.get(f"/albums/{album_id}"))
        if album.id != album_id:
            raise SpotifyError(502, "spotify_invalid_response")
        result = MonthlyAlbum(**album.model_dump(), trackDetailsUnavailable=bool(track_id))
        spotify_cache.remember_metadata(self.connection, album_id, track_id, result)
        return result

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
