"""PostgreSQL integration tests; each test creates and drops its own schema."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.seed import LOCAL_SPOTIFY_ACCOUNT_ID, LOCAL_USERNAME, seed_local_user
from app.models import Profile, User
from app.repositories import profiles, sessions, spotify_connections, users
from app.services.accounts import create_user_with_profile


@pytest.fixture
def run_db():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")

    def run(scenario):
        async def execute():
            schema = f"test_{uuid4().hex}"
            admin = create_async_engine(url)
            engine = None
            try:
                async with admin.begin() as connection:
                    await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                engine = create_async_engine(
                    url, connect_args={"server_settings": {"search_path": schema}}
                )
                async with engine.begin() as connection:
                    await connection.run_sync(Base.metadata.create_all)
                await scenario(async_sessionmaker(engine, expire_on_commit=False))
            finally:
                if engine is not None:
                    await engine.dispose()
                async with admin.begin() as connection:
                    await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                await admin.dispose()

        asyncio.run(execute())

    return run


def test_account_commit_and_identity_constraints(run_db):
    async def scenario(factory):
        async with factory() as db:
            user, profile = await create_user_with_profile(
                db,
                spotify_account_id="account-1",
                username="tester",
                display_name="Test",
            )
        async with factory() as db:
            assert (
                await users.get_by_id(db, user.id)
            ).spotify_account_id == "account-1"
            assert (await profiles.get_by_username(db, "tester")).id == profile.id
        async with factory() as db:
            with pytest.raises(IntegrityError):
                await create_user_with_profile(
                    db,
                    spotify_account_id="account-1",
                    username="other",
                    display_name="X",
                )
            assert await db.scalar(select(func.count()).select_from(User)) == 1
        async with factory() as db:
            with pytest.raises(IntegrityError):
                await create_user_with_profile(
                    db,
                    spotify_account_id="account-2",
                    username="tester",
                    display_name="X",
                )
            # The profile conflict must also roll back the newly inserted user.
            assert await users.get_by_spotify_account_id(db, "account-2") is None
            assert await db.scalar(select(func.count()).select_from(Profile)) == 1

    run_db(scenario)


def test_repository_rollback_and_profile_update(run_db):
    async def scenario(factory):
        async with factory() as db:
            with pytest.raises(RuntimeError):
                async with db.begin():
                    await users.create(db, spotify_account_id="rolled-back")
                    raise RuntimeError("abort")
        async with factory() as db:
            assert await users.get_by_spotify_account_id(db, "rolled-back") is None
        async with factory() as db:
            user, _ = await create_user_with_profile(
                db, spotify_account_id="account", username="tester", display_name="Test"
            )
            async with db.begin():
                profile = await profiles.get_by_user_id(db, user.id)
                await profiles.update(
                    db, profile, bio="Updated", theme={"color": "blue"}
                )
        async with factory() as db:
            profile = await profiles.get_by_user_id(db, user.id)
            assert profile.bio == "Updated"
            assert profile.theme == {"color": "blue"}

    run_db(scenario)


def test_session_lifecycle_and_connection_upsert(run_db):
    async def scenario(factory):
        async with factory() as db, db.begin():
            user = await users.create(db, spotify_account_id="account")
            await spotify_connections.upsert(
                db,
                user_id=user.id,
                encrypted_refresh_token="ciphertext-1",
                scopes="read",
            )
            connection = await spotify_connections.upsert(
                db,
                user_id=user.id,
                encrypted_refresh_token="ciphertext-2",
                scopes="read write",
            )
            assert connection.encrypted_refresh_token == "ciphertext-2"
            now = datetime.now(UTC)
            session = await sessions.create(
                db,
                token="opaque-token",
                user_id=user.id,
                expires_at=now + timedelta(hours=1),
            )
            assert session.id == sessions.token_digest("opaque-token")
            assert session.id != "opaque-token"
            await sessions.create(
                db,
                token="expired",
                user_id=user.id,
                expires_at=now - timedelta(seconds=1),
            )
        async with factory() as db, db.begin():
            assert await sessions.get_active(db, "opaque-token") is not None
            assert await sessions.get_active(db, "expired") is None
            assert await sessions.get_active(db, "unknown") is None
            assert (
                await spotify_connections.get_by_user_id(db, user.id)
            ).scopes == "read write"
            assert await sessions.delete_expired(db) == 1
            await sessions.delete_by_token(db, "opaque-token")
        async with factory() as db:
            assert await sessions.get_active(db, "opaque-token") is None

    run_db(scenario)


def test_seed_is_idempotent_and_preserves_edits(run_db):
    async def scenario(factory):
        async with factory() as db:
            await seed_local_user(db)
            async with db.begin():
                profile = await profiles.get_by_username(db, LOCAL_USERNAME)
                await profiles.update(db, profile, display_name="Edited")
            await seed_local_user(db)
        async with factory() as db:
            assert await db.scalar(select(func.count()).select_from(User)) == 1
            assert await db.scalar(select(func.count()).select_from(Profile)) == 1
            assert await users.get_by_spotify_account_id(db, LOCAL_SPOTIFY_ACCOUNT_ID)
            assert (
                await profiles.get_by_username(db, LOCAL_USERNAME)
            ).display_name == "Edited"

    run_db(scenario)
