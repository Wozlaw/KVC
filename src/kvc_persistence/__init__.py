"""PostgreSQL persistence foundation."""

from kvc_persistence.base import Base
from kvc_persistence.engine import (
    DatabaseConfigurationError,
    create_async_engine_from_settings,
    dispose_async_engine,
    get_database_url,
)
from kvc_persistence.health import DatabaseHealthResult, check_database_connection
from kvc_persistence.session import create_async_sessionmaker

__all__ = [
    "Base",
    "DatabaseConfigurationError",
    "DatabaseHealthResult",
    "check_database_connection",
    "create_async_engine_from_settings",
    "create_async_sessionmaker",
    "dispose_async_engine",
    "get_database_url",
]
