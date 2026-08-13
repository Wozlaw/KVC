"""Application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnvironment = Literal["development", "test", "production"]


class AppSettings(BaseSettings):
    """Settings loaded from environment variables with safe bootstrap defaults."""

    model_config = SettingsConfigDict(
        env_prefix="KVC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "Kaiten Voice Control"
    app_env: AppEnvironment = "development"
    log_level: str = "INFO"
    database_url: SecretStr | None = None
    database_echo: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_blank_database_url(cls, value: object) -> object:
        if value == "":
            return None
        return value


@lru_cache
def get_settings() -> AppSettings:
    """Return cached application settings."""

    return AppSettings()
