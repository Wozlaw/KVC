"""Live PostgreSQL acceptance for MAX dispatcher identity integration."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kvc_api.max import UpdateDispatcher
from kvc_application.services import IdentityService
from kvc_config import get_settings
from kvc_integrations.max.dto import MaxIncomingUpdate, MaxSentMessage
from kvc_persistence import (
    create_async_engine_from_settings,
    create_async_sessionmaker,
    dispose_async_engine,
)
from kvc_persistence.models import KaitenConnection, MaxChat, NotificationSetting, User
from kvc_persistence.repositories import MaxChatRepository, NotificationSettingsRepository

EXPECTED_REVISION = "00201_mvp_service_model"


@pytest_asyncio.fixture
async def live_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    if settings.app_env != "development":
        pytest.skip("MAX dispatcher integration tests require KVC_APP_ENV=development.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip("MAX dispatcher integration tests require the kvc_dev database.")

            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip("MAX dispatcher integration tests require the accepted Alembic head.")

        yield engine
    finally:
        await dispose_async_engine(engine)


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


class FakeSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def send_text_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        format: None = None,
        notify: bool = True,
    ) -> MaxSentMessage:
        self.calls.append((chat_id, text))
        return MaxSentMessage(message_id="mid-out", chat_id=chat_id, timestamp=3)


@dataclass(frozen=True)
class DispatcherPgContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    prefix: str
    sender: FakeSender
    dispatcher: UpdateDispatcher

    def private_update(self, user_suffix: str, chat_suffix: str) -> MaxIncomingUpdate:
        return MaxIncomingUpdate(
            source="webhook",
            update_type="message_created",
            timestamp=1,
            raw_event_type="message_created",
            chat_id=f"{self.prefix}-chat-{chat_suffix}",
            chat_type="PRIVATE",
            max_user_id=f"{self.prefix}-user-{user_suffix}",
            message_id="mid-1",
            message_text="/start",
            message_timestamp=2,
            callback_payload=None,
        )


@pytest_asyncio.fixture
async def dispatcher_pg_context(
    live_engine: AsyncEngine,
) -> AsyncIterator[DispatcherPgContext]:
    prefix = f"synthetic-max-dispatcher-{uuid.uuid4()}"
    sessionmaker = create_async_sessionmaker(live_engine)
    sender = FakeSender()
    context = DispatcherPgContext(
        engine=live_engine,
        sessionmaker=sessionmaker,
        prefix=prefix,
        sender=sender,
        dispatcher=UpdateDispatcher(
            identity_service=IdentityService(sessionmaker),
            message_sender=sender,
            allowed_update_types=("message_created", "message_callback", "bot_started"),
        ),
    )
    try:
        yield context
    finally:
        await cleanup_identity_rows(live_engine, prefix)


async def load_binding(context: DispatcherPgContext, max_user_id: str) -> MaxChat | None:
    async with context.sessionmaker() as session:
        return await MaxChatRepository(session).get_private_by_max_user_id(max_user_id)


async def load_settings(
    context: DispatcherPgContext,
    user_id: uuid.UUID,
) -> NotificationSetting | None:
    async with context.sessionmaker() as session:
        return await NotificationSettingsRepository(session).get_for_user(user_id)


async def count_bindings(context: DispatcherPgContext, max_user_id: str) -> int:
    async with context.sessionmaker() as session:
        bindings = (
            (await session.execute(select(MaxChat).where(MaxChat.max_user_id == max_user_id)))
            .scalars()
            .all()
        )
        return len(bindings)


@pytest.mark.asyncio
async def test_dispatcher_private_start_creates_identity_and_is_idempotent(
    dispatcher_pg_context: DispatcherPgContext,
) -> None:
    update = dispatcher_pg_context.private_update("u1", "c1")

    first = await dispatcher_pg_context.dispatcher.dispatch(update)
    second = await dispatcher_pg_context.dispatcher.dispatch(update)

    binding = await load_binding(dispatcher_pg_context, update.max_user_id or "")
    assert binding is not None
    settings = await load_settings(dispatcher_pg_context, binding.user_id)
    assert settings is not None
    assert first.identity_resolved is True
    assert second.identity_resolved is True
    assert await count_bindings(dispatcher_pg_context, update.max_user_id or "") == 1


@pytest.mark.asyncio
async def test_dispatcher_private_start_rotates_same_user_chat_binding(
    dispatcher_pg_context: DispatcherPgContext,
) -> None:
    first_update = dispatcher_pg_context.private_update("u1", "c1")
    second_update = dispatcher_pg_context.private_update("u1", "c2")

    await dispatcher_pg_context.dispatcher.dispatch(first_update)
    await dispatcher_pg_context.dispatcher.dispatch(second_update)

    binding = await load_binding(dispatcher_pg_context, first_update.max_user_id or "")
    assert binding is not None
    assert binding.max_chat_id == second_update.chat_id
    assert await count_bindings(dispatcher_pg_context, first_update.max_user_id or "") == 1


@pytest.mark.asyncio
async def test_dispatcher_group_update_does_not_create_identity(
    dispatcher_pg_context: DispatcherPgContext,
) -> None:
    update = MaxIncomingUpdate(
        source="webhook",
        update_type="message_created",
        timestamp=1,
        raw_event_type="message_created",
        chat_id=f"{dispatcher_pg_context.prefix}-group",
        chat_type="GROUP",
        max_user_id=f"{dispatcher_pg_context.prefix}-user-group",
        message_id="mid-1",
        message_text="/start",
        message_timestamp=2,
        callback_payload=None,
    )

    await dispatcher_pg_context.dispatcher.dispatch(update)

    assert await count_bindings(dispatcher_pg_context, update.max_user_id or "") == 0
