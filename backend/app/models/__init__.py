"""Import models together to register all tables on Base.metadata."""

from app.models.artwork_remix import ArtworkRemix
from app.models.monthly_mosaic import MonthlyMosaic
from app.models.mosaic import Mosaic
from app.models.profile import Profile
from app.models.session import Session
from app.models.spotify_connection import SpotifyConnection
from app.models.user import User

__all__ = [
    "ArtworkRemix",
    "MonthlyMosaic",
    "Mosaic",
    "Profile",
    "Session",
    "SpotifyConnection",
    "User",
]
