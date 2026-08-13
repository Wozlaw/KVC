"""Async SQLAlchemy engine factory."""

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from kvc_config import AppSettings, get_settings

POSTGRESQL_ASYNCPG_DRIVER = "postgresql+asyncpg"


class DatabaseConfigurationError(RuntimeError):
    """Raised when database infrastructure cannot be configured safely."""


def get_database_url(settings: AppSettings | None = None) -> str:
    """Return the validated SQLAlchemy database URL for engine creation."""

    app_settings = settings or get_settings()
    if app_settings.database_url is None:
        raise DatabaseConfigurationError("KVC_DATABASE_URL is required for database access.")

    raw_url = app_settings.database_url.get_secret_value()
    if not raw_url:
        raise DatabaseConfigurationError("KVC_DATABASE_URL is required for database access.")

    try:
        parsed_url = make_url(raw_url)
    except ArgumentError as exc:
        raise DatabaseConfigurationError(
            "KVC_DATABASE_URL must be a valid SQLAlchemy URL."
        ) from exc

    if parsed_url.drivername != POSTGRESQL_ASYNCPG_DRIVER:
        raise DatabaseConfigurationError("KVC_DATABASE_URL must use the postgresql+asyncpg driver.")

    return raw_url


def create_async_engine_from_settings(settings: AppSettings | None = None) -> AsyncEngine:
    """Create an AsyncEngine without opening a network connection."""

    app_settings = settings or get_settings()
    database_url = get_database_url(app_settings)
    return create_async_engine(
        database_url,
        echo=app_settings.database_echo,
        pool_pre_ping=True,
    )


async def dispose_async_engine(engine: AsyncEngine) -> None:
    """Dispose an AsyncEngine during tests or application shutdown."""

    await engine.dispose()
