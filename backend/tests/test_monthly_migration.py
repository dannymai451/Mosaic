"""Track-provenance migration preserves previously archived artwork."""

import asyncio
import json
import os
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from test_albums import ALBUM_A, ALBUM_B

from app.models import MonthlyMosaic
from app.services.monthly_mosaic import monthly_layout
from app.services.mosaic import expand_preset


def test_track_provenance_migration_backfills_empty_mapping_and_preserves_layout(
    migrated_database_url,
):
    name = f"mosaic_monthly_migration_{uuid4().hex}"
    source = os.environ["TEST_DATABASE_URL"]
    target = make_url(source).set(database=name).render_as_string(hide_password=False)
    user_id, profile_id, mosaic_id = uuid4(), uuid4(), uuid4()
    albums = [ALBUM_A, ALBUM_B]
    layout = expand_preset("heart", albums).model_dump()
    earlier_id = uuid4()

    async def admin(sql):
        engine = create_async_engine(source, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                await connection.execute(text(sql))
        finally:
            await engine.dispose()

    def migrate(*args):
        subprocess.run(
            ["uv", "run", "--locked", "alembic", *args],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "DATABASE_URL": target},
            check=True,
        )

    async def old_snapshot():
        engine = create_async_engine(target)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO users (id, spotify_account_id) VALUES (:id, 'migration-owner')"
                    ),
                    {"id": user_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO profiles (id, user_id, username, display_name) VALUES (:id, :user_id, 'migration_owner', 'Migration owner')"
                    ),
                    {"id": profile_id, "user_id": user_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO monthly_mosaics (id, profile_id, month, generated_at, source_track_count, album_ids, preset_key, grid_width, grid_height, tiles) VALUES (:id, :profile_id, :month, :generated_at, 1, CAST(:album_ids AS jsonb), 'heart', 9, 9, CAST(:tiles AS jsonb))"
                    ),
                    {
                        "id": mosaic_id,
                        "profile_id": profile_id,
                        "month": date(2026, 10, 1),
                        "generated_at": datetime(2026, 10, 1, tzinfo=UTC),
                        "album_ids": json.dumps(albums),
                        "tiles": json.dumps(layout["tiles"]),
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO monthly_mosaics (id, profile_id, month, generated_at, source_track_count, album_ids, preset_key, grid_width, grid_height, tiles) SELECT :id, profile_id, DATE '2026-09-01', generated_at, source_track_count, album_ids, preset_key, grid_width, grid_height, tiles FROM monthly_mosaics WHERE id = :original"
                    ),
                    {"id": earlier_id, "original": mosaic_id},
                )
        finally:
            await engine.dispose()

    async def upgraded_snapshot():
        engine = create_async_engine(target, poolclass=NullPool)
        try:
            factory = async_sessionmaker(engine)
            async with factory() as db:
                snapshot = await db.get(MonthlyMosaic, mosaic_id)
                assert snapshot.representative_track_ids == {}
                assert snapshot.album_ids == albums
                assert snapshot.preset_key == "heart"
                assert snapshot.tiles == layout["tiles"]
        finally:
            await engine.dispose()

    asyncio.run(admin(f'CREATE DATABASE "{name}"'))
    try:
        migrate("upgrade", "f83d16729a4c")
        asyncio.run(old_snapshot())
        migrate("upgrade", "a04c98be76d2")
        asyncio.run(upgraded_snapshot())
        migrate("downgrade", "f83d16729a4c")
        migrate("upgrade", "a04c98be76d2")
        asyncio.run(upgraded_snapshot())
        asyncio.run(
            assert_october_correction(
                target, migrate, mosaic_id, earlier_id, albums, layout
            )
        )
    finally:
        asyncio.run(admin(f'DROP DATABASE "{name}" WITH (FORCE)'))


async def assert_october_correction(
    target, migrate, mosaic_id, earlier_id, albums, layout
):
    engine = create_async_engine(target, poolclass=NullPool)
    provenance = {ALBUM_A: "0123456789012345678901"}
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE monthly_mosaics SET representative_track_ids=CAST(:tracks AS jsonb) WHERE id=:id"
                ),
                {"tracks": json.dumps(provenance), "id": mosaic_id},
            )
        factory = async_sessionmaker(engine)
        migrate("upgrade", "b17ea42c093d")
        async with factory() as db:
            original = await db.get(MonthlyMosaic, mosaic_id)
            old_tiles = [
                {**tile, **({"spotifyTrackId": f"{index:022d}"} if index % 2 == 0 else {})}
                for index, tile in enumerate(original.tiles)
            ]
            original.tiles = old_tiles
            await db.commit()
        migrate("upgrade", "head")
        async with factory() as db:
            corrected = await db.get(MonthlyMosaic, mosaic_id)
            assert corrected.preset_key == "pumpkin"
            shape = monthly_layout(date(2026, 10, 1), albums)[1]
            assert corrected.grid_width == corrected.grid_height == 12
            assert corrected.tiles == [
                {**old_tiles[index % len(old_tiles)], "x": tile.x, "y": tile.y}
                for index, tile in enumerate(shape.tiles)
            ]
            corrected_tiles = corrected.tiles
            assert {tile.get("spotifyTrackId") for tile in corrected.tiles} == {
                tile.get("spotifyTrackId") for tile in old_tiles
            }
            assert corrected.album_ids == albums
            assert corrected.representative_track_ids == provenance
            assert corrected.generated_at == datetime(2026, 10, 1, tzinfo=UTC)
            assert corrected.month == date(2026, 10, 1)
            assert corrected.source_track_count == 1
            assert (
                corrected.profile_id
                == (await db.get(MonthlyMosaic, earlier_id)).profile_id
            )
            earlier = await db.get(MonthlyMosaic, earlier_id)
            assert earlier.preset_key == "heart"
            assert earlier.tiles == layout["tiles"]
        # Re-running migration history must not reselect music or undo the correction.
        migrate("downgrade", "a04c98be76d2")
        migrate("upgrade", "head")
        async with factory() as db:
            corrected = await db.get(MonthlyMosaic, mosaic_id)
            assert corrected.preset_key == "pumpkin"
            assert corrected.representative_track_ids == provenance
            assert corrected.tiles == corrected_tiles
    finally:
        await engine.dispose()
