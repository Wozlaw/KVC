"""Application settings."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AppEnvironment = Literal["development", "test", "production"]
MaxInboundMode = Literal["webhook", "long_polling"]

DEFAULT_MAX_ALLOWED_UPDATE_TYPES = (
    "message_created",
    "message_callback",
    "bot_started",
)


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
    token_encryption_active_version: int | None = None
    token_encryption_keys: SecretStr | None = None
    max_bot_token: SecretStr | None = None
    max_api_base_url: str = "https://platform-api2.max.ru"
    max_webhook_secret: SecretStr | None = None
    max_webhook_path: str = "/max/webhook"
    max_inbound_mode: MaxInboundMode = "webhook"
    max_allowed_update_types: Annotated[tuple[str, ...], NoDecode] = (
        DEFAULT_MAX_ALLOWED_UPDATE_TYPES
    )
    max_polling_timeout_seconds: int = 60
    max_polling_limit: int = 100
    max_webhook_public_url: str | None = None
    max_mini_app_public_url: str | None = None
    max_mini_app_context_secret: SecretStr | None = None

    @field_validator(
        "database_url",
        "token_encryption_keys",
        "max_bot_token",
        "max_webhook_secret",
        "max_mini_app_context_secret",
        mode="before",
    )
    @classmethod
    def normalize_blank_secret(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("max_webhook_public_url", "max_mini_app_public_url", mode="before")
    @classmethod
    def normalize_blank_optional_url(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("token_encryption_active_version", mode="before")
    @classmethod
    def normalize_blank_token_encryption_active_version(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("max_allowed_update_types", mode="before")
    @classmethod
    def normalize_max_allowed_update_types(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("max_allowed_update_types")
    @classmethod
    def validate_max_allowed_update_types(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("MAX allowed update types must not be empty")
        return value

    @field_validator("max_polling_timeout_seconds")
    @classmethod
    def validate_max_polling_timeout_seconds(cls, value: int) -> int:
        if not 0 <= value <= 90:
            raise ValueError("MAX polling timeout must be between 0 and 90 seconds")
        return value

    @field_validator("max_polling_limit")
    @classmethod
    def validate_max_polling_limit(cls, value: int) -> int:
        if not 1 <= value <= 1000:
            raise ValueError("MAX polling limit must be between 1 and 1000")
        return value


@lru_cache
def get_settings() -> AppSettings:
    """Return cached application settings."""

    return AppSettings()
