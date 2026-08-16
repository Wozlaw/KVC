"""Persistence foundation tests."""

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from kvc_config import AppSettings
from kvc_persistence import (
    Base,
    DatabaseConfigurationError,
    check_database_connection,
    create_async_engine_from_settings,
    create_async_sessionmaker,
    dispose_async_engine,
    get_database_url,
)
from kvc_persistence import models as _models

TEST_DATABASE_URL = "postgresql+asyncpg://user:password@127.0.0.1:5432/kvc_test"


def test_base_metadata_contains_mvp_business_tables() -> None:
    assert _models.User.__tablename__ == "users"
    assert set(Base.metadata.tables) == {
        "users",
        "max_chats",
        "kaiten_connections",
        "dialog_sessions",
        "pending_commands",
        "notification_settings",
        "notification_history",
    }


def test_base_metadata_naming_convention() -> None:
    convention = Base.metadata.naming_convention

    assert convention["ix"] == "ix_%(column_0_label)s"
    assert convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    assert convention["ck"] == "ck_%(table_name)s_%(constraint_name)s"
    assert convention["fk"] == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    assert convention["pk"] == "pk_%(table_name)s"


def test_get_database_url_requires_postgresql_asyncpg() -> None:
    settings = AppSettings(database_url=SecretStr("postgresql://user:password@localhost/db"))

    with pytest.raises(DatabaseConfigurationError, match="postgresql\\+asyncpg"):
        get_database_url(settings)


@pytest.mark.asyncio
async def test_engine_factory_creates_async_engine_without_connecting() -> None:
    settings = AppSettings(database_url=SecretStr(TEST_DATABASE_URL))

    engine = create_async_engine_from_settings(settings)
    try:
        assert isinstance(engine, AsyncEngine)
        assert engine.url.drivername == "postgresql+asyncpg"
        assert engine.url.database == "kvc_test"
    finally:
        await dispose_async_engine(engine)


@pytest.mark.asyncio
async def test_sessionmaker_contract() -> None:
    settings = AppSettings(database_url=SecretStr(TEST_DATABASE_URL))
    engine = create_async_engine_from_settings(settings)
    try:
        session_factory = create_async_sessionmaker(engine)

        assert session_factory.class_ is AsyncSession
        assert session_factory.kw["expire_on_commit"] is False
    finally:
        await dispose_async_engine(engine)


class FakeResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one(self) -> object:
        return self.value


class FakeConnection:
    def __init__(self) -> None:
        self.statement_text = ""

    async def execute(self, statement: object) -> FakeResult:
        self.statement_text = str(statement)
        return FakeResult(1)


class FakeConnectionContext:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.exited = False

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> bool | None:
        self.exited = True
        return None


class FakeEngine:
    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.context = FakeConnectionContext(self.connection)

    def connect(self) -> FakeConnectionContext:
        return self.context


class FailingEngine:
    def connect(self) -> FakeConnectionContext:
        raise RuntimeError("connection failed")


@pytest.mark.asyncio
async def test_database_health_probe_success() -> None:
    engine = FakeEngine()

    result = await check_database_connection(engine)

    assert result.ok is True
    assert result.error_type is None
    assert engine.connection.statement_text == "SELECT 1"
    assert engine.context.exited is True


@pytest.mark.asyncio
async def test_database_health_probe_returns_safe_failure() -> None:
    result = await check_database_connection(FailingEngine())

    assert result.ok is False
    assert result.error_type == "RuntimeError"
