"""Opt-in local fixture: uv run python -m app.db.seed --local."""

import argparse
import asyncio

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import profiles, users

LOCAL_SPOTIFY_ACCOUNT_ID = "mosaic-local-test-user"
LOCAL_USERNAME = "mosaic_local_test"


async def seed_local_user(db: AsyncSession) -> None:
    """Create one fixture atomically; repeated runs preserve existing profile edits."""
    async with db.begin():
        # The unique account key serializes simultaneous seed runs.
        statement = insert(User).values(spotify_account_id=LOCAL_SPOTIFY_ACCOUNT_ID)
        await db.execute(
            statement.on_conflict_do_update(
                index_elements=[User.spotify_account_id],
                set_={"spotify_account_id": statement.excluded.spotify_account_id},
            )
        )
        user = await users.get_by_spotify_account_id(db, LOCAL_SPOTIFY_ACCOUNT_ID)
        if await profiles.get_by_user_id(db, user.id) is None:
            await profiles.create(
                db,
                user_id=user.id,
                username=LOCAL_USERNAME,
                display_name="Local Test User",
                bio="Local development fixture for Mosaic.",
            )


async def main() -> None:
    from app.db.session import AsyncSessionLocal, engine

    try:
        async with AsyncSessionLocal() as db:
            await seed_local_user(db)
        print(f"Local fixture ready: {LOCAL_USERNAME}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true", required=True)
    parser.parse_args()
    asyncio.run(main())
