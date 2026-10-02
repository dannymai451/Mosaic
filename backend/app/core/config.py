from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str
    frontend_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()