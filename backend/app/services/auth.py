"""Atomic Spotify account linking and durable application sessions."""

import secrets
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories import profiles, sessions, spotify_connections, users


async def persist_login(db: AsyncSession, profile: dict, tokens: dict) -> str:
    account_id = profile.get("account_id")
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("spotify_profile_failed")
    if not settings.token_encryption_key:
        raise ValueError("token_encryption_not_configured")
    cipher = Fernet(settings.token_encryption_key)
    session_token = secrets.token_urlsafe(32)
    async with db.begin():
        user = await users.upsert(db, spotify_account_id=account_id)
        connection = await spotify_connections.get_by_user_id(db, user.id)
        refresh_token = tokens.get("refresh_token")
        if not refresh_token and connection is None:
            raise ValueError("missing_refresh_token")
        await spotify_connections.upsert(
            db,
            user_id=user.id,
            encrypted_refresh_token=(
                cipher.encrypt(refresh_token.encode()).decode()
                if refresh_token
                else connection.encrypted_refresh_token
            ),
            scopes=tokens.get("scope", connection.scopes if connection else ""),
        )
        local_profile = await profiles.get_by_user_id(db, user.id)
        if local_profile is None:
            local_profile = await profiles.create(
                db,
                user_id=user.id,
                username=f"user_{user.id.hex[:25]}",
                display_name=profile.get("display_name") or "Spotify user",
            )
        images = profile.get("images") or []
        local_profile.avatar_url = images[0].get("url") if images else None
        await sessions.create(
            db,
            token=session_token,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    return session_token
