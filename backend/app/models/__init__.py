"""Import models together to register all tables on Base.metadata."""

from app.models.profile import Profile
from app.models.session import Session
from app.models.spotify_connection import SpotifyConnection
from app.models.user import User

__all__ = ["Profile", "Session", "SpotifyConnection", "User"]
