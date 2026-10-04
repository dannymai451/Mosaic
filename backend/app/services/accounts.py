"""Account operations own transactions; pass a fresh session to each operation."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, User
from app.repositories import profiles, users


async def create_user_with_profile(
    db: AsyncSession, *, spotify_account_id: str, username: str, display_name: str
) -> tuple[User, Profile]:
    """Commit both rows together, or roll back both on any error."""
    async with db.begin():
        user = await users.create(db, spotify_account_id=spotify_account_id)
        profile = await profiles.create(
            db, user_id=user.id, username=username, display_name=display_name
        )
    return user, profile
