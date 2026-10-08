"""Bounded, process-local Spotify caches. Never persist or return cached tokens."""

import asyncio
import hashlib
from collections import OrderedDict
from concurrent.futures import Future
from contextlib import asynccontextmanager
from threading import Lock
from time import monotonic
from uuid import UUID

from app.core.config import settings
from app.models import SpotifyConnection
from app.schemas.monthly_mosaic import MonthlyAlbum

METADATA_TTL = 300
TOKEN_EXPIRY_MARGIN = 30


class TTLCache[K, V]:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._entries: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry[0] <= monotonic():
                self._entries.pop(key)
                return None
            self._entries.move_to_end(key)
            return entry[1]

    def put(self, key: K, value: V, expires_at: float) -> None:
        with self._lock:
            now = monotonic()
            for expired in [
                k for k, (deadline, _) in self._entries.items() if deadline <= now
            ]:
                self._entries.pop(expired)
            if expires_at <= now:
                return
            self._entries[key] = (expires_at, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self.capacity:
                self._entries.popitem(last=False)

    def discard(self, key: K) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


type ConnectionKey = tuple[UUID, str]
type MetadataKey = tuple[ConnectionKey, str, str | None]

access_tokens = TTLCache[ConnectionKey, str](256)
monthly_metadata = TTLCache[MetadataKey, MonthlyAlbum](4096)
_refreshes: dict[UUID, Future[None]] = {}
_refresh_lock = Lock()


@asynccontextmanager
async def serialized_refresh(user_id: UUID):
    """Serialize refresh through post-commit publication, across request loops."""
    while True:
        with _refresh_lock:
            pending = _refreshes.get(user_id)
            if pending is None:
                current: Future[None] = Future()
                _refreshes[user_id] = current
                break
        # Cancellation of one waiter must not cancel another request's refresh.
        await asyncio.shield(asyncio.wrap_future(pending))
    try:
        yield
    finally:
        with _refresh_lock:
            _refreshes.pop(user_id)
        current.set_result(None)


def connection_key(connection: SpotifyConnection) -> ConnectionKey:
    # Reconnect, scope changes, token rotation, and encryption-key changes invalidate
    # reuse. Hash the credential version rather than retaining it in cache keys.
    version = "\0".join(
        [
            connection.encrypted_refresh_token,
            connection.scopes,
            settings.spotify_client_id,
            settings.token_encryption_key or "",
        ]
    )
    return connection.user_id, hashlib.sha256(version.encode()).hexdigest()


def token_deadline(expires_in: object, issued_at: float) -> float:
    # Missing/malformed lifetimes must never create an indefinitely reusable token.
    if type(expires_in) is not int or expires_in <= TOKEN_EXPIRY_MARGIN:
        return issued_at
    return issued_at + min(expires_in, 3600) - TOKEN_EXPIRY_MARGIN


def remember_metadata(
    connection: SpotifyConnection,
    album_id: str,
    track_id: str | None,
    album: MonthlyAlbum,
) -> None:
    if not album.trackDetailsUnavailable:
        monthly_metadata.put(
            (connection_key(connection), album_id, track_id),
            album.model_copy(deep=True),
            monotonic() + METADATA_TTL,
        )
