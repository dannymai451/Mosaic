"""Disposable PostgreSQL databases migrated from blank for integration tests."""

import asyncio
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

os.environ.setdefault("SPOTIFY_CLIENT_ID", "test-client-id")
os.environ.setdefault("SPOTIFY_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault(
    "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/api/auth/spotify/callback"
)
os.environ.setdefault("FRONTEND_URL", "http://127.0.0.1:3000")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost/unused"
)
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())


@pytest.fixture(scope="session")
def migrated_database_url():
    source = os.environ.get("TEST_DATABASE_URL")
    if not source:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    name = f"mosaic_test_{uuid4().hex}"
    url = make_url(source).set(database=name).render_as_string(hide_password=False)

    async def admin(sql):
        engine = create_async_engine(source, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                await connection.execute(text(sql))
        finally:
            await engine.dispose()

    asyncio.run(admin(f'CREATE DATABASE "{name}"'))
    try:
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "DATABASE_URL": url},
            check=True,
        )
        yield url
    finally:
        asyncio.run(admin(f'DROP DATABASE "{name}" WITH (FORCE)'))


@pytest.fixture
def database_client(migrated_database_url):
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy.pool import NullPool

    from app.db.session import get_db
    from app.main import app

    engine = create_async_engine(migrated_database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())
