"""Live PostgreSQL integration tests for IdentityService."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kvc_application.dto import ResolveMaxIdentityInput
from kvc_application.errors import IdentityConflict
from kvc_application.services import IdentityService
from kvc_config import get_settings
from kvc_persistence import (
    create_async_engine_from_settings,
    create_async_sessionmaker,
    dispose_async_engine,
)
from kvc_persistence.models import KaitenConnection, MaxChat, NotificationSetting, User
from kvc_persistence.repositories import (
    KaitenConnectionRepository,
    MaxChatRepository,
    NotificationSettingsRepository,
    UserRepository,
)

EXPECTED_REVISION = "00201_mvp_service_model"
BUSINESS_TABLES = (
    "dialog_sessions",
    "kaiten_connections",
    "max_chats",
    "notification_history",
    "notification_settings",
    "pending_commands",
    "users",
)


@pytest_asyncio.fixture
async def live_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    if settings.app_env != "development":
        pytest.skip("IdentityService integration tests require KVC_APP_ENV=development.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip("IdentityService integration tests require the kvc_dev database.")

            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip("IdentityService integration tests require the accepted Alembic head.")

        yield engine
    finally:
        await dispose_async_engine(engine)


async def table_counts(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as conn:
        counts = {}
        for table_name in BUSINESS_TABLES:
            counts[table_name] = (
                await conn.execute(text(f"SELECT count(*) FROM {table_name}"))
            ).scalar_one()
        return counts


async def cleanup_identity_rows(engine: AsyncEngine, prefix: str) -> None:
    async with engine.begin() as conn:
        user_ids = (
            (
                await conn.execute(
                    select(MaxChat.user_id).where(MaxChat.max_user_id.like(f"{prefix}%")).distinct()
                )
            )
            .scalars()
            .all()
        )

        if user_ids:
            await conn.execute(
                delete(NotificationSetting).where(NotificationSetting.user_id.in_(user_ids))
            )
            await conn.execute(
                delete(KaitenConnection).where(KaitenConnection.user_id.in_(user_ids))
            )
            await conn.execute(delete(MaxChat).where(MaxChat.user_id.in_(user_ids)))
            await conn.execute(delete(User).where(User.id.in_(user_ids)))


@dataclass(frozen=True)
class IdentityContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    prefix: str
    service: IdentityService

    def input(self, user_suffix: str, chat_suffix: str) -> ResolveMaxIdentityInput:
        return ResolveMaxIdentityInput(
            max_user_id=f"{self.prefix}-user-{user_suffix}",
            max_chat_id=f"{self.prefix}-chat-{chat_suffix}",
            chat_type="PRIVATE",
        )


@pytest_asyncio.fixture
async def identity_context(live_engine: AsyncEngine) -> AsyncIterator[IdentityContext]:
    prefix = f"synthetic-identity-{uuid.uuid4()}"
    sessionmaker = create_async_sessionmaker(live_engine)
    context = IdentityContext(
        engine=live_engine,
        sessionmaker=sessionmaker,
        prefix=prefix,
        service=IdentityService(sessionmaker),
    )
    try:
        yield context
    finally:
        await cleanup_identity_rows(live_engine, prefix)


async def load_binding(context: IdentityContext, max_user_id: str) -> MaxChat:
    async with context.sessionmaker() as session:
        binding = await MaxChatRepository(session).get_private_by_max_user_id(max_user_id)
        assert binding is not None
        return binding


async def load_settings(context: IdentityContext, user_id: uuid.UUID) -> NotificationSetting:
    async with context.sessionmaker() as session:
        settings = await NotificationSettingsRepository(session).get_for_user(user_id)
        assert settings is not None
        return settings


async def count_bindings(context: IdentityContext, max_user_id: str) -> int:
    async with context.sessionmaker() as session:
        bindings = (
            (await session.execute(select(MaxChat).where(MaxChat.max_user_id == max_user_id)))
            .scalars()
            .all()
        )
        return len(bindings)


async def test_identity_service_onboards_new_user_with_default_settings(
    identity_context: IdentityContext,
) -> None:
    input = identity_context.input("u1", "c1")

    result = await identity_context.service.resolve_or_onboard_private_max_user(input)

    assert result.is_new_user is True
    assert result.user_status == "ACTIVE"
    assert result.kaiten_connection_status is None

    binding = await load_binding(identity_context, input.max_user_id)
    assert binding.id == result.max_chat_binding_id
    assert binding.user_id == result.user_id
    assert binding.max_chat_id == input.max_chat_id
    assert binding.chat_type == "PRIVATE"
    assert binding.is_primary is True

    settings = await load_settings(identity_context, result.user_id)
    assert settings.enabled is False
    assert settings.due_soon_days == 1
    assert settings.timezone == "UTC"


async def test_identity_service_repeated_resolution_is_idempotent(
    identity_context: IdentityContext,
) -> None:
    input = identity_context.input("u1", "c1")

    first = await identity_context.service.resolve_or_onboard_private_max_user(input)
    second = await identity_context.service.resolve_or_onboard_private_max_user(input)

    assert first.user_id == second.user_id
    assert first.max_chat_binding_id == second.max_chat_binding_id
    assert first.is_new_user is True
    assert second.is_new_user is False
    assert await count_bindings(identity_context, input.max_user_id) == 1


async def test_identity_service_projects_existing_kaiten_connection_status(
    identity_context: IdentityContext,
) -> None:
    input = identity_context.input("u1", "c1")
    first = await identity_context.service.resolve_or_onboard_private_max_user(input)
    async with identity_context.sessionmaker() as session:
        async with session.begin():
            await KaitenConnectionRepository(session).create(
                user_id=first.user_id,
                api_base_url="https://synthetic-kaiten.example",
                encrypted_api_token=b"synthetic-ciphertext",
                status="NEEDS_REAUTH",
            )

    second = await identity_context.service.resolve_or_onboard_private_max_user(input)

    assert second.user_id == first.user_id
    assert second.kaiten_connection_status == "NEEDS_REAUTH"


async def test_identity_service_resolves_disabled_user(
    identity_context: IdentityContext,
) -> None:
    input = identity_context.input("u1", "c1")
    first = await identity_context.service.resolve_or_onboard_private_max_user(input)
    async with identity_context.sessionmaker() as session:
        async with session.begin():
            user = await UserRepository(session).get_by_id_for_update(first.user_id)
            assert user is not None
            await UserRepository(session).set_status(user, "DISABLED")

    second = await identity_context.service.resolve_or_onboard_private_max_user(input)

    assert second.user_id == first.user_id
    assert second.user_status == "DISABLED"
    assert second.is_new_user is False


async def test_identity_service_safely_rotates_chat_id(
    identity_context: IdentityContext,
) -> None:
    first_input = identity_context.input("u1", "c1")
    rotated_input = identity_context.input("u1", "c2")
    first = await identity_context.service.resolve_or_onboard_private_max_user(first_input)

    rotated = await identity_context.service.resolve_or_onboard_private_max_user(rotated_input)
    binding = await load_binding(identity_context, first_input.max_user_id)
    repeated = await identity_context.service.resolve_or_onboard_private_max_user(rotated_input)

    assert rotated.user_id == first.user_id
    assert rotated.max_chat_binding_id == first.max_chat_binding_id
    assert rotated.is_new_user is False
    assert binding.id == first.max_chat_binding_id
    assert binding.max_chat_id == rotated_input.max_chat_id
    assert binding.max_user_id == first_input.max_user_id
    assert binding.chat_type == "PRIVATE"
    assert binding.is_primary is True
    assert repeated.user_id == first.user_id
    assert repeated.max_chat_binding_id == first.max_chat_binding_id
    assert repeated.is_new_user is False
    assert await count_bindings(identity_context, first_input.max_user_id) == 1


async def test_identity_service_rotates_disabled_user_without_reenable(
    identity_context: IdentityContext,
) -> None:
    first_input = identity_context.input("u1", "c1")
    rotated_input = identity_context.input("u1", "c2")
    first = await identity_context.service.resolve_or_onboard_private_max_user(first_input)
    async with identity_context.sessionmaker() as session:
        async with session.begin():
            user = await UserRepository(session).get_by_id_for_update(first.user_id)
            assert user is not None
            await UserRepository(session).set_status(user, "DISABLED")

    rotated = await identity_context.service.resolve_or_onboard_private_max_user(rotated_input)

    assert rotated.user_id == first.user_id
    assert rotated.max_chat_binding_id == first.max_chat_binding_id
    assert rotated.user_status == "DISABLED"
    assert rotated.is_new_user is False


async def test_identity_service_rejects_chat_user_mismatch(
    identity_context: IdentityContext,
) -> None:
    first_input = identity_context.input("u1", "c1")
    await identity_context.service.resolve_or_onboard_private_max_user(first_input)

    with pytest.raises(IdentityConflict):
        await identity_context.service.resolve_or_onboard_private_max_user(
            ResolveMaxIdentityInput(
                max_user_id=f"{identity_context.prefix}-user-u2",
                max_chat_id=first_input.max_chat_id,
                chat_type="PRIVATE",
            )
        )


async def test_identity_service_rejects_occupied_rotation_chat(
    identity_context: IdentityContext,
) -> None:
    first_input = identity_context.input("u1", "c1")
    second_input = identity_context.input("u2", "c2")
    await identity_context.service.resolve_or_onboard_private_max_user(first_input)
    second = await identity_context.service.resolve_or_onboard_private_max_user(second_input)

    with pytest.raises(IdentityConflict):
        await identity_context.service.resolve_or_onboard_private_max_user(
            ResolveMaxIdentityInput(
                max_user_id=first_input.max_user_id,
                max_chat_id=second_input.max_chat_id,
                chat_type="PRIVATE",
            )
        )

    binding = await load_binding(identity_context, second_input.max_user_id)
    assert binding.id == second.max_chat_binding_id
    assert binding.max_chat_id == second_input.max_chat_id


async def test_identity_onboarding_rollback_prevents_partial_rows(
    identity_context: IdentityContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input = identity_context.input("u1", "c1")

    async def fail_settings_creation(
        self: NotificationSettingsRepository,
        user_id: uuid.UUID,
    ) -> None:
        raise RuntimeError("synthetic settings failure")

    monkeypatch.setattr(
        NotificationSettingsRepository,
        "get_or_create_for_user",
        fail_settings_creation,
    )

    with pytest.raises(RuntimeError, match="synthetic settings failure"):
        await identity_context.service.resolve_or_onboard_private_max_user(input)

    async with identity_context.sessionmaker() as session:
        assert (
            await MaxChatRepository(session).get_private_by_max_user_id(input.max_user_id) is None
        )


async def test_identity_service_integration_database_stays_clean(
    live_engine: AsyncEngine,
) -> None:
    assert await table_counts(live_engine) == {table_name: 0 for table_name in BUSINESS_TABLES}
