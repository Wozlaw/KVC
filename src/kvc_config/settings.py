"""Application settings."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Settings loaded from environment variables with safe bootstrap defaults."""

    model_config = SettingsConfigDict(
        env_prefix="KVC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "Kaiten Voice Control"
    env: str = "development"
    log_level: str = "INFO"
    database_url: str = ""
    max_bot_token: SecretStr | None = None
    max_webhook_secret: SecretStr | None = None
    kaiten_api_token: SecretStr | None = None
    gigachat_credentials: SecretStr | None = None
    gigachat_model: str = "GigaChat-Pro"
    stt_provider: str = ""
    salutespeech_auth_key: SecretStr | None = None
    token_encryption_key: SecretStr | None = Field(default=None)


@lru_cache
def get_settings() -> AppSettings:
    """Return cached application settings."""

    return AppSettings()
