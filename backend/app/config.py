from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    base_path: str = "/wot"
    public_url: str = "http://localhost:8000/wot"
    database_url: str = "postgresql+asyncpg://wot:wot@db:5432/wot"
    secret_key: str = Field(min_length=32)
    token_encryption_key: str = Field(min_length=44, max_length=44)
    session_hours: int = 24
    twitch_client_id: str = ""
    twitch_client_secret: str = ""
    twitch_redirect_uri: str = "http://localhost:8000/wot/api/oauth/twitch/callback"
    twitch_embed_parent: str = "localhost"
    sync_interval_seconds: int = 60
    source_sync_hours: int = 6
    source_user_agent: str = "WoT-Twitch-Drops-Dashboard/1.0 (+https://gry.lemanczyk-it.pl/wot/)"
    cors_origins: str = ""
    notification_types: str = "start_24h,start_1h,start,end_2h,reward,claim,stream_interrupted,oauth_expired"
    discord_webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""
    @property
    def secure_cookies(self) -> bool:
        return self.public_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
