"""Live PostgreSQL acceptance for MAX Long Polling shared transport."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kvc_api.max import build_max_runtime
from kvc_config import AppSettings, get_settings
from kvc_integrations.max import MaxLongPollingRunner, MaxLongPollingSource
from kvc_persistence import (
    create_async_engine_from_settings,
    create_async_sessionmaker,
    dispose_async_engine,
)
from kvc_persistence.models import KaitenConnection, MaxChat, NotificationSetting, User
from kvc_persistence.repositories import MaxChatRepository, NotificationSettingsRepository

EXPECTED_REVISION = "00201_mvp_service_model"
TOKEN_MARKER = "SYNTHETIC-LONG-POLLING-TOKEN"


@pytest_asyncio.fixture
async def live_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    if settings.app_env != "development":
        pytest.skip("MAX Long Polling integration tests require KVC_APP_ENV=development.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip("MAX Long Polling integration tests require the kvc_dev database.")

            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip("MAX Long Polling integration tests require the accepted Alembic head.")

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


def raw_private_update(prefix: str, *, user_suffix: str, chat_suffix: str) -> dict[str, object]:
    return {
        "update_type": "message_created",
        "timestamp": 1_700_000_000_000,
        "message": {
            "sender": {"user_id": f"{prefix}-user-{user_suffix}"},
            "recipient": {"chat_id": f"{prefix}-chat-{chat_suffix}", "chat_type": "dialog"},
            "timestamp": 1_700_000_000_001,
            "body": {"mid": "mid-1", "text": "/start"},
        },
    }


def raw_group_update(prefix: str) -> dict[str, object]:
    return {
        "update_type": "message_created",
        "timestamp": 1_700_000_000_000,
        "message": {
            "sender": {"user_id": f"{prefix}-user-group"},
            "recipient": {"chat_id": f"{prefix}-group", "chat_type": "chat"},
            "timestamp": 1_700_000_000_001,
            "body": {"mid": "mid-1", "text": "/start"},
        },
    }


@dataclass
class MockMaxProvider:
    batches: list[dict[str, object]]
    requests: list[httpx.Request]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/updates" and request.method == "GET":
            return httpx.Response(200, json=self.batches.pop(0))
        if request.url.path == "/messages" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "timestamp": 1_700_000_000_002,
                        "recipient": {"chat_id": request.url.params.get("chat_id")},
                        "body": {"mid": "mid-out"},
                    }
                },
            )
        return httpx.Response(404)

    @property
    def update_requests(self) -> list[httpx.Request]:
        return [request for request in self.requests if request.url.path == "/updates"]


@dataclass(frozen=True)
class LongPollingPgContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    prefix: str


@pytest_asyncio.fixture
async def long_polling_pg_context(
    live_engine: AsyncEngine,
) -> AsyncIterator[LongPollingPgContext]:
    prefix = f"synthetic-max-long-polling-{uuid.uuid4()}"
    context = LongPollingPgContext(
        engine=live_engine,
        sessionmaker=create_async_sessionmaker(live_engine),
        prefix=prefix,
    )
    try:
        yield context
    finally:
        await cleanup_identity_rows(live_engine, prefix)


async def run_scripted_polling(
    context: LongPollingPgContext,
    batches: list[dict[str, object]],
) -> MockMaxProvider:
    provider = MockMaxProvider(batches=batches, requests=[])
    settings = AppSettings(
        max_inbound_mode="long_polling",
        max_bot_token=SecretStr(TOKEN_MARKER),
        max_allowed_update_types=("message_created", "message_callback", "bot_started"),
        max_polling_limit=100,
        max_polling_timeout_seconds=60,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider.handler)) as http_client:
        runtime = build_max_runtime(
            settings=settings,
            http_client=http_client,
            sessionmaker=context.sessionmaker,
        )
        source = MaxLongPollingSource(
            runtime.api_client,
            limit=settings.max_polling_limit,
            timeout_seconds=settings.max_polling_timeout_seconds,
            update_types=settings.max_allowed_update_types,
        )
        await MaxLongPollingRunner(
            source=source,
            dispatcher=runtime.dispatcher,
        ).run(max_cycles=len(batches))
    return provider


async def load_binding(context: LongPollingPgContext, max_user_id: str) -> MaxChat | None:
    async with context.sessionmaker() as session:
        return await MaxChatRepository(session).get_private_by_max_user_id(max_user_id)


async def load_settings(
    context: LongPollingPgContext,
    user_id: uuid.UUID,
) -> NotificationSetting | None:
    async with context.sessionmaker() as session:
        return await NotificationSettingsRepository(session).get_for_user(user_id)


async def count_bindings(context: LongPollingPgContext, max_user_id: str) -> int:
    async with context.sessionmaker() as session:
        bindings = (
            (await session.execute(select(MaxChat).where(MaxChat.max_user_id == max_user_id)))
            .scalars()
            .all()
        )
        return len(bindings)


@pytest.mark.asyncio
async def test_long_polling_private_start_is_idempotent_across_poll_cycles(
    long_polling_pg_context: LongPollingPgContext,
) -> None:
    update = raw_private_update(long_polling_pg_context.prefix, user_suffix="u1", chat_suffix="c1")
    provider = await run_scripted_polling(
        long_polling_pg_context,
        [
            {"updates": [update], "marker": 10},
            {"updates": [update], "marker": 20},
            {"updates": [], "marker": 30},
        ],
    )

    max_user_id = f"{long_polling_pg_context.prefix}-user-u1"
    binding = await load_binding(long_polling_pg_context, max_user_id)
    assert binding is not None
    settings = await load_settings(long_polling_pg_context, binding.user_id)
    assert settings is not None
    assert await count_bindings(long_polling_pg_context, max_user_id) == 1
    assert [dict(request.url.params).get("marker") for request in provider.update_requests] == [
        None,
        "10",
        "20",
    ]
    assert all(
        request.headers.get("Authorization") == TOKEN_MARKER for request in provider.requests
    )
    assert all(TOKEN_MARKER not in str(request.url) for request in provider.requests)


@pytest.mark.asyncio
async def test_long_polling_private_start_rotates_same_user_chat_binding(
    long_polling_pg_context: LongPollingPgContext,
) -> None:
    await run_scripted_polling(
        long_polling_pg_context,
        [
            {
                "updates": [
                    raw_private_update(
                        long_polling_pg_context.prefix,
                        user_suffix="u1",
                        chat_suffix="c1",
                    )
                ],
                "marker": 10,
            },
            {
                "updates": [
                    raw_private_update(
                        long_polling_pg_context.prefix,
                        user_suffix="u1",
                        chat_suffix="c2",
                    )
                ],
                "marker": 20,
            },
        ],
    )

    max_user_id = f"{long_polling_pg_context.prefix}-user-u1"
    binding = await load_binding(long_polling_pg_context, max_user_id)
    assert binding is not None
    assert binding.max_chat_id == f"{long_polling_pg_context.prefix}-chat-c2"
    assert await count_bindings(long_polling_pg_context, max_user_id) == 1


@pytest.mark.asyncio
async def test_long_polling_group_update_does_not_create_identity(
    long_polling_pg_context: LongPollingPgContext,
) -> None:
    await run_scripted_polling(
        long_polling_pg_context,
        [{"updates": [raw_group_update(long_polling_pg_context.prefix)], "marker": 10}],
    )

    assert (
        await count_bindings(
            long_polling_pg_context,
            f"{long_polling_pg_context.prefix}-user-group",
        )
        == 0
    )
