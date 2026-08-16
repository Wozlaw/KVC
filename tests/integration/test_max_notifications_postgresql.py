"""Live PostgreSQL acceptance for MAX notification settings Mini App."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kvc_api.main import create_app
from kvc_api.max.dispatcher import UpdateDispatcher
from kvc_api.max.mini_app import MAX_INIT_DATA_HEADER, MAX_MINI_APP_CONTEXT_HEADER
from kvc_api.max.runtime import MaxMiniAppRuntime
from kvc_api.max.service_commands import ServiceCommandHandler
from kvc_application.services import IdentityService, NotificationSettingsService
from kvc_config import AppSettings, get_settings
from kvc_integrations.max.context_signing import MiniAppContextSigner
from kvc_integrations.max.dto import MaxIncomingUpdate, MaxSentMessage
from kvc_persistence import (
    create_async_engine_from_settings,
    create_async_sessionmaker,
    dispose_async_engine,
)
from kvc_persistence.models import (
    DialogSession,
    KaitenConnection,
    MaxChat,
    NotificationHistory,
    NotificationSetting,
    PendingCommand,
    User,
)

EXPECTED_REVISION = "00201_mvp_service_model"
BOT_TOKEN = "synthetic-bot-token"
CONTEXT_SECRET = "synthetic-context-secret"
BUSINESS_TABLES = (
    "dialog_sessions",
    "kaiten_connections",
    "max_chats",
    "notification_history",
    "notification_settings",
    "pending_commands",
    "users",
)


class FakeSender:
    def __init__(self) -> None:
        self.text_calls: list[tuple[str, str]] = []
        self.open_app_calls: list[tuple[str, str, str, str, str | None]] = []

    async def send_text_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        format: None = None,
        notify: bool = True,
    ) -> MaxSentMessage:
        self.text_calls.append((chat_id, text))
        return MaxSentMessage(message_id="mid-out", chat_id=chat_id, timestamp=3)

    async def send_open_app_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        context_ref: str,
        label: str,
        app_path: str | None = None,
        format: None = None,
        notify: bool = True,
    ) -> MaxSentMessage:
        self.open_app_calls.append((chat_id, text, context_ref, label, app_path))
        return MaxSentMessage(message_id="mid-out", chat_id=chat_id, timestamp=3)


@dataclass
class NotificationsPgContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    baseline_counts: dict[str, int]
    sender: FakeSender
    max_user_ids: list[str]

    def dispatcher(self) -> UpdateDispatcher:
        return UpdateDispatcher(
            identity_resolver_factory=lambda: IdentityService(self.sessionmaker),
            message_sender=self.sender,
            service_command_handler=ServiceCommandHandler(
                context_signer=MiniAppContextSigner(CONTEXT_SECRET),
                mini_app_launch_enabled=True,
                now=lambda: int(time.time()),
            ),
            allowed_update_types=("message_created", "message_callback", "bot_started"),
        )

    def app(self) -> object:
        runtime = MaxMiniAppRuntime(
            identity_resolver_factory=lambda: IdentityService(self.sessionmaker),
            kaiten_connection_binder_factory=lambda: object(),  # type: ignore[arg-type]
            message_sender=self.sender,
            context_signer=MiniAppContextSigner(CONTEXT_SECRET),
            notification_settings_service_factory=lambda: NotificationSettingsService(
                self.sessionmaker
            ),
        )
        settings = AppSettings(
            max_bot_token=SecretStr(BOT_TOKEN),
            max_mini_app_context_secret=SecretStr(CONTEXT_SECRET),
        )
        return create_app(settings, max_mini_app_runtime=runtime)


@pytest_asyncio.fixture
async def live_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    if settings.app_env != "development":
        pytest.skip("MAX notification settings PostgreSQL acceptance requires development env.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip("MAX notification settings PostgreSQL acceptance requires kvc_dev.")

            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip("MAX notification settings PostgreSQL acceptance requires head.")

        yield engine
    finally:
        await dispose_async_engine(engine)


@pytest_asyncio.fixture
async def notifications_context(
    live_engine: AsyncEngine,
) -> AsyncIterator[NotificationsPgContext]:
    context = NotificationsPgContext(
        engine=live_engine,
        sessionmaker=create_async_sessionmaker(live_engine),
        baseline_counts=await table_counts(live_engine),
        sender=FakeSender(),
        max_user_ids=[],
    )
    try:
        yield context
    finally:
        await cleanup_max_users(live_engine, context.max_user_ids)
        assert await table_counts(live_engine) == context.baseline_counts


@pytest.mark.asyncio
async def test_notification_settings_lifecycle_acceptance(
    notifications_context: NotificationsPgContext,
) -> None:
    max_user_id = _unique_id("max-user")
    max_chat_id = _unique_id("max-chat")
    notifications_context.max_user_ids.append(max_user_id)

    await dispatch_command(notifications_context, "/start", max_user_id, max_chat_id)
    user_id = await user_id_for_max_user(notifications_context, max_user_id)
    defaults = await settings_for_user(notifications_context, user_id)
    assert (defaults.enabled, defaults.due_soon_days, defaults.timezone) == (False, 1, "UTC")

    await dispatch_command(notifications_context, "/notifications", max_user_id, max_chat_id)
    context_ref = notifications_context.sender.open_app_calls[-1][2]
    assert notifications_context.sender.open_app_calls[-1][4] == "/max/app/notifications"

    first_get = await mini_app_get(
        notifications_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=context_ref,
    )
    assert first_get == {"enabled": False, "due_soon_days": 1, "timezone": "UTC"}

    first_save = await mini_app_post(
        notifications_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=context_ref,
        payload={"enabled": False, "due_soon_days": 3, "timezone": "UTC"},
    )
    assert first_save["status"] == "saved"
    assert first_save["confirmation_status"] == "sent"
    assert await settings_tuple(notifications_context, user_id) == (False, 3, "UTC")
    assert len(notifications_context.sender.text_calls) == 2

    after_invalid = await mini_app_post_response(
        notifications_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=context_ref,
        payload={"enabled": True, "due_soon_days": 31, "timezone": "UTC"},
    )
    assert after_invalid.status_code == 400
    assert after_invalid.json() == {"status": "invalid_settings"}
    assert await settings_tuple(notifications_context, user_id) == (False, 3, "UTC")
    assert len(notifications_context.sender.text_calls) == 2

    reopened_context = await open_notifications(
        notifications_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
    )
    reopened_get = await mini_app_get(
        notifications_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=reopened_context,
    )
    assert reopened_get == {"enabled": False, "due_soon_days": 3, "timezone": "UTC"}

    second_save = await mini_app_post(
        notifications_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=reopened_context,
        payload={"enabled": True, "due_soon_days": 1, "timezone": "Europe/Warsaw"},
    )
    assert second_save["settings"] == {
        "enabled": True,
        "due_soon_days": 1,
        "timezone": "Europe/Warsaw",
    }
    assert await settings_tuple(notifications_context, user_id) == (True, 1, "Europe/Warsaw")

    assert await notification_settings_count(notifications_context, user_id) == 1
    assert await notification_history_count(notifications_context, user_id) == 0
    assert await kaiten_connection_count(notifications_context, user_id) == 0


@pytest.mark.asyncio
async def test_disabled_user_and_cross_user_context_are_rejected(
    notifications_context: NotificationsPgContext,
) -> None:
    first_user = _unique_id("max-user")
    first_chat = _unique_id("max-chat")
    second_user = _unique_id("max-user")
    second_chat = _unique_id("max-chat")
    notifications_context.max_user_ids.extend([first_user, second_user])

    first_context = await open_notifications(
        notifications_context,
        max_user_id=first_user,
        max_chat_id=first_chat,
    )
    first_user_id = await user_id_for_max_user(notifications_context, first_user)
    await set_user_status(notifications_context, first_user_id, "DISABLED")

    disabled_get = await mini_app_get_response(
        notifications_context,
        max_user_id=first_user,
        max_chat_id=first_chat,
        context_ref=first_context,
    )
    disabled_post = await mini_app_post_response(
        notifications_context,
        max_user_id=first_user,
        max_chat_id=first_chat,
        context_ref=first_context,
        payload={"enabled": True, "due_soon_days": 3, "timezone": "UTC"},
    )
    assert disabled_get.status_code == 403
    assert disabled_get.json() == {"status": "user_disabled"}
    assert disabled_post.status_code == 403
    assert disabled_post.json() == {"status": "user_disabled"}
    assert await settings_tuple(notifications_context, first_user_id) == (False, 1, "UTC")

    await dispatch_command(notifications_context, "/start", second_user, second_chat)
    second_user_id = await user_id_for_max_user(notifications_context, second_user)
    cross_user = await mini_app_post_response(
        notifications_context,
        max_user_id=second_user,
        max_chat_id=second_chat,
        context_ref=first_context,
        payload={"enabled": True, "due_soon_days": 3, "timezone": "UTC"},
    )
    assert cross_user.status_code == 403
    assert cross_user.json() == {"status": "invalid_context"}
    assert await settings_tuple(notifications_context, second_user_id) == (False, 1, "UTC")


async def dispatch_command(
    context: NotificationsPgContext,
    command: str,
    max_user_id: str,
    max_chat_id: str,
) -> None:
    outcome = await context.dispatcher().dispatch(
        MaxIncomingUpdate(
            source="webhook",
            update_type="message_created",
            timestamp=1,
            raw_event_type="message_created",
            chat_id=max_chat_id,
            chat_type="PRIVATE",
            max_user_id=max_user_id,
            message_id="mid-1",
            message_text=command,
            message_timestamp=2,
            callback_payload=None,
        )
    )
    assert outcome.response_sent is True


async def open_notifications(
    context: NotificationsPgContext,
    *,
    max_user_id: str,
    max_chat_id: str,
) -> str:
    await dispatch_command(context, "/notifications", max_user_id, max_chat_id)
    return context.sender.open_app_calls[-1][2]


async def mini_app_get(
    context: NotificationsPgContext,
    *,
    max_user_id: str,
    max_chat_id: str,
    context_ref: str,
) -> dict[str, object]:
    response = await mini_app_get_response(
        context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=context_ref,
    )
    assert response.status_code == 200
    return dict(response.json())


async def mini_app_get_response(
    context: NotificationsPgContext,
    *,
    max_user_id: str,
    max_chat_id: str,
    context_ref: str,
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=context.app()),
        base_url="http://testserver",
    ) as client:
        return await client.get(
            "/max/app/api/notifications",
            headers=headers(max_user_id, max_chat_id, context_ref),
        )


async def mini_app_post(
    context: NotificationsPgContext,
    *,
    max_user_id: str,
    max_chat_id: str,
    context_ref: str,
    payload: dict[str, object],
) -> dict[str, object]:
    response = await mini_app_post_response(
        context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=context_ref,
        payload=payload,
    )
    assert response.status_code == 200
    return dict(response.json())


async def mini_app_post_response(
    context: NotificationsPgContext,
    *,
    max_user_id: str,
    max_chat_id: str,
    context_ref: str,
    payload: dict[str, object],
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=context.app()),
        base_url="http://testserver",
    ) as client:
        return await client.post(
            "/max/app/api/notifications",
            headers=headers(max_user_id, max_chat_id, context_ref),
            json=payload,
        )


def headers(max_user_id: str, max_chat_id: str, context_ref: str) -> dict[str, str]:
    return {
        MAX_INIT_DATA_HEADER: signed_init_data(
            max_user_id=max_user_id,
            max_chat_id=max_chat_id,
            start_param=context_ref,
        ),
        MAX_MINI_APP_CONTEXT_HEADER: context_ref,
    }


async def table_counts(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as conn:
        counts = {}
        for table_name in BUSINESS_TABLES:
            counts[table_name] = (
                await conn.execute(text(f"SELECT count(*) FROM {table_name}"))
            ).scalar_one()
        return counts


async def cleanup_max_users(engine: AsyncEngine, max_user_ids: list[str]) -> None:
    if not max_user_ids:
        return
    async with engine.begin() as conn:
        user_ids = (
            (
                await conn.execute(
                    select(MaxChat.user_id).where(MaxChat.max_user_id.in_(max_user_ids))
                )
            )
            .scalars()
            .all()
        )
        if not user_ids:
            return
        await conn.execute(
            delete(NotificationHistory).where(NotificationHistory.user_id.in_(user_ids))
        )
        await conn.execute(delete(PendingCommand).where(PendingCommand.user_id.in_(user_ids)))
        await conn.execute(delete(DialogSession).where(DialogSession.user_id.in_(user_ids)))
        await conn.execute(
            delete(NotificationSetting).where(NotificationSetting.user_id.in_(user_ids))
        )
        await conn.execute(delete(KaitenConnection).where(KaitenConnection.user_id.in_(user_ids)))
        await conn.execute(delete(MaxChat).where(MaxChat.user_id.in_(user_ids)))
        await conn.execute(delete(User).where(User.id.in_(user_ids)))


async def user_id_for_max_user(context: NotificationsPgContext, max_user_id: str) -> uuid.UUID:
    async with context.sessionmaker() as session:
        user_id = (
            await session.execute(select(MaxChat.user_id).where(MaxChat.max_user_id == max_user_id))
        ).scalar_one_or_none()
        assert user_id is not None
        return user_id


async def settings_for_user(
    context: NotificationsPgContext,
    user_id: uuid.UUID,
) -> NotificationSetting:
    async with context.sessionmaker() as session:
        row = (
            await session.execute(
                select(NotificationSetting).where(NotificationSetting.user_id == user_id)
            )
        ).scalar_one_or_none()
        assert row is not None
        return row


async def settings_tuple(
    context: NotificationsPgContext,
    user_id: uuid.UUID,
) -> tuple[bool, int, str]:
    row = await settings_for_user(context, user_id)
    return row.enabled, row.due_soon_days, row.timezone


async def notification_settings_count(context: NotificationsPgContext, user_id: uuid.UUID) -> int:
    async with context.sessionmaker() as session:
        return len(
            (
                await session.execute(
                    select(NotificationSetting).where(NotificationSetting.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )


async def notification_history_count(context: NotificationsPgContext, user_id: uuid.UUID) -> int:
    async with context.sessionmaker() as session:
        return len(
            (
                await session.execute(
                    select(NotificationHistory).where(NotificationHistory.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )


async def kaiten_connection_count(context: NotificationsPgContext, user_id: uuid.UUID) -> int:
    async with context.sessionmaker() as session:
        return len(
            (
                await session.execute(
                    select(KaitenConnection).where(KaitenConnection.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )


async def set_user_status(
    context: NotificationsPgContext,
    user_id: uuid.UUID,
    status: str,
) -> None:
    async with context.engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET status = :status WHERE id = :user_id"),
            {"status": status, "user_id": user_id},
        )


def signed_init_data(*, max_user_id: str, max_chat_id: str, start_param: str) -> str:
    params = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": max_user_id}, separators=(",", ":")),
        "chat": json.dumps({"id": max_chat_id, "type": "dialog"}, separators=(",", ":")),
        "start_param": start_param,
    }
    data_check_string = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(params) + f"&hash={signature}"


def _unique_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"
