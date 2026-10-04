"""Run migrations using the application's model metadata and asyncpg driver."""

import asyncio
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app import models  # noqa: F401 — register every model on Base.metadata
from app.db.base import Base


class MigrationSettings(BaseSettings):
    # Migrations need only database configuration, not Spotify credentials.
    database_url: str

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL without connecting to the database."""
    context.configure(
        url=MigrationSettings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(
        MigrationSettings().database_url, poolclass=pool.NullPool
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
