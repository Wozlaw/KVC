"""Live PostgreSQL acceptance for MAX contextual Mini App interactions."""

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
from kvc_api.max.mini_app import MAX_INIT_DATA_HEADER, MAX_MINI_APP_CONTEXT_HEADER
from kvc_api.max.runtime import MaxMiniAppRuntime
from kvc_application.dto import (
    ContextInteractionOption,
    ContextInteractionResult,
    ContextInteractionView,
    ResolveMaxIdentityInput,
)
from kvc_application.errors import (
    ContextInteractionAlreadyCompleted,
    ContextInteractionInvalidSelection,
)
from kvc_application.services import IdentityService
from kvc_config import AppSettings, get_settings
from kvc_integrations.max.context_signing import MiniAppContextPurpose, MiniAppContextSigner
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
WORKFLOW_REF = "synthetic-choice-001"
BUSINESS_TABLES = (
    "dialog_sessions",
    "kaiten_connections",
    "max_chats",
    "notification_history",
    "notification_settings",
    "pending_commands",
    "users",
)


class FakeContextResolver:
    def __init__(self) -> None:
        self.completed: set[tuple[uuid.UUID, str]] = set()
        self.get_calls: list[tuple[uuid.UUID, str]] = []
        self.submit_calls: list[tuple[uuid.UUID, str, str]] = []
        self.cancel_calls: list[tuple[uuid.UUID, str]] = []

    async def get_interaction(
        self,
        *,
        user_id: uuid.UUID,
        workflow_ref: str,
    ) -> ContextInteractionView:
        self.get_calls.append((user_id, workflow_ref))
        if (user_id, workflow_ref) in self.completed:
            raise ContextInteractionAlreadyCompleted("synthetic")
        return ContextInteractionView(
            workflow_ref,
            "Выберите карточку",
            "Найдены несколько вариантов.",
            [
                ContextInteractionOption("one", "Первый вариант"),
                ContextInteractionOption("two", "Второй вариант"),
            ],
        )

    async def submit_selection(
        self,
        *,
        user_id: uuid.UUID,
        workflow_ref: str,
        option_id: str,
    ) -> ContextInteractionResult:
        self.submit_calls.append((user_id, workflow_ref, option_id))
        if (user_id, workflow_ref) in self.completed:
            raise ContextInteractionAlreadyCompleted("synthetic")
        if option_id not in {"one", "two"}:
            raise ContextInteractionInvalidSelection("synthetic")
        self.completed.add((user_id, workflow_ref))
        return ContextInteractionResult("completed", "Выбор принят.")

    async def cancel_interaction(
        self,
        *,
        user_id: uuid.UUID,
        workflow_ref: str,
    ) -> ContextInteractionResult:
        self.cancel_calls.append((user_id, workflow_ref))
        if (user_id, workflow_ref) in self.completed:
            raise ContextInteractionAlreadyCompleted("synthetic")
        self.completed.add((user_id, workflow_ref))
        return ContextInteractionResult("cancelled")


class FakeSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def send_text_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        notify: bool = True,
    ) -> object:
        self.calls.append((chat_id, text))
        return object()


@dataclass
class ContextInteractionPgContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    baseline_counts: dict[str, int]
    resolver: FakeContextResolver
    sender: FakeSender
    max_user_ids: list[str]

    def app(self) -> object:
        runtime = MaxMiniAppRuntime(
            identity_resolver_factory=lambda: IdentityService(self.sessionmaker),
            kaiten_connection_binder_factory=lambda: object(),  # type: ignore[arg-type]
            message_sender=self.sender,
            context_signer=MiniAppContextSigner(CONTEXT_SECRET),
            context_interaction_resolver_factory=lambda: self.resolver,
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
        pytest.skip("MAX contextual Mini App PostgreSQL acceptance requires development env.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip("MAX contextual Mini App PostgreSQL acceptance requires kvc_dev.")

            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip("MAX contextual Mini App PostgreSQL acceptance requires head.")

        yield engine
    finally:
        await dispose_async_engine(engine)


@pytest_asyncio.fixture
async def pg_context(
    live_engine: AsyncEngine,
) -> AsyncIterator[ContextInteractionPgContext]:
    context = ContextInteractionPgContext(
        engine=live_engine,
        sessionmaker=create_async_sessionmaker(live_engine),
        baseline_counts=await table_counts(live_engine),
        resolver=FakeContextResolver(),
        sender=FakeSender(),
        max_user_ids=[],
    )
    try:
        yield context
    finally:
        await cleanup_max_users(live_engine, context.max_user_ids)
        assert await table_counts(live_engine) == context.baseline_counts


@pytest.mark.asyncio
async def test_context_interaction_uses_real_identity_and_no_local_workflow_tables(
    pg_context: ContextInteractionPgContext,
) -> None:
    max_user_id = _unique_id("max-user")
    max_chat_id = _unique_id("max-chat")
    pg_context.max_user_ids.append(max_user_id)
    user_id = await onboard_user(pg_context, max_user_id, max_chat_id)
    context_ref = context_ref_for(max_user_id, max_chat_id)

    loaded = await mini_app_get(
        pg_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=context_ref,
    )
    assert loaded["title"] == "Выберите карточку"
    assert loaded["options"] == [
        {"id": "one", "label": "Первый вариант", "description": None},
        {"id": "two", "label": "Второй вариант", "description": None},
    ]

    submitted = await mini_app_post(
        pg_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=context_ref,
        payload={"selected_option_id": "two"},
    )
    assert submitted == {"status": "completed", "confirmation_status": "sent"}
    assert pg_context.resolver.submit_calls == [(user_id, WORKFLOW_REF, "two")]
    assert pg_context.sender.calls == [(max_chat_id, "Выбор принят.")]
    assert await dialog_session_count(pg_context, user_id) == 0
    assert await pending_command_count(pg_context, user_id) == 0
    assert await kaiten_connection_count(pg_context, user_id) == 0
    assert await notification_history_count(pg_context, user_id) == 0


@pytest.mark.asyncio
async def test_context_interaction_rejects_cross_user_chat_rotation_and_disabled_user(
    pg_context: ContextInteractionPgContext,
) -> None:
    first_user = _unique_id("max-user")
    first_chat = _unique_id("max-chat")
    second_user = _unique_id("max-user")
    second_chat = _unique_id("max-chat")
    pg_context.max_user_ids.extend([first_user, second_user])

    first_user_id = await onboard_user(pg_context, first_user, first_chat)
    await onboard_user(pg_context, second_user, second_chat)
    first_context = context_ref_for(first_user, first_chat)

    resolver_call_count = len(pg_context.resolver.get_calls)
    cross_user = await mini_app_get_response(
        pg_context,
        max_user_id=second_user,
        max_chat_id=second_chat,
        context_ref=first_context,
    )
    assert cross_user.status_code == 403
    assert cross_user.json() == {"status": "invalid_context"}
    assert len(pg_context.resolver.get_calls) == resolver_call_count

    old_chat_context = context_ref_for(first_user, first_chat)
    rotated_chat = _unique_id("max-chat")
    rotated_old = await mini_app_get_response(
        pg_context,
        max_user_id=first_user,
        max_chat_id=rotated_chat,
        context_ref=old_chat_context,
    )
    assert rotated_old.status_code == 403
    assert rotated_old.json() == {"status": "invalid_context"}
    assert len(pg_context.resolver.get_calls) == resolver_call_count

    fresh_rotated_context = context_ref_for(first_user, rotated_chat)
    rotated_fresh = await mini_app_get_response(
        pg_context,
        max_user_id=first_user,
        max_chat_id=rotated_chat,
        context_ref=fresh_rotated_context,
    )
    assert rotated_fresh.status_code == 200
    assert pg_context.resolver.get_calls[-1] == (first_user_id, WORKFLOW_REF)

    await set_user_status(pg_context, first_user_id, "DISABLED")
    resolver_call_count = len(pg_context.resolver.get_calls)
    disabled_get = await mini_app_get_response(
        pg_context,
        max_user_id=first_user,
        max_chat_id=rotated_chat,
        context_ref=fresh_rotated_context,
    )
    disabled_post = await mini_app_post_response(
        pg_context,
        max_user_id=first_user,
        max_chat_id=rotated_chat,
        context_ref=fresh_rotated_context,
        payload={"selected_option_id": "one"},
    )
    assert disabled_get.status_code == 403
    assert disabled_get.json() == {"status": "user_disabled"}
    assert disabled_post.status_code == 403
    assert disabled_post.json() == {"status": "user_disabled"}
    assert len(pg_context.resolver.get_calls) == resolver_call_count
    assert pg_context.resolver.submit_calls == []


async def onboard_user(
    context: ContextInteractionPgContext,
    max_user_id: str,
    max_chat_id: str,
) -> uuid.UUID:
    identity = await IdentityService(context.sessionmaker).resolve_or_onboard_private_max_user(
        ResolveMaxIdentityInput(max_user_id, max_chat_id, "PRIVATE")
    )
    return identity.user_id


async def mini_app_get(
    context: ContextInteractionPgContext,
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
    context: ContextInteractionPgContext,
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
            "/max/app/api/context",
            headers=headers(max_user_id, max_chat_id, context_ref),
        )


async def mini_app_post(
    context: ContextInteractionPgContext,
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
    context: ContextInteractionPgContext,
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
            "/max/app/api/context",
            headers=headers(max_user_id, max_chat_id, context_ref),
            json=payload,
        )


def headers(max_user_id: str, max_chat_id: str, context_ref: str) -> dict[str, str]:
    return {
        MAX_INIT_DATA_HEADER: signed_init_data(max_user_id, max_chat_id, context_ref),
        MAX_MINI_APP_CONTEXT_HEADER: context_ref,
    }


def context_ref_for(max_user_id: str, max_chat_id: str) -> str:
    signer = MiniAppContextSigner(CONTEXT_SECRET)
    binding = signer.make_identity_binding(max_user_id=max_user_id, chat_id=max_chat_id)
    return signer.issue(
        purpose=MiniAppContextPurpose.SYNTHETIC_CONTEXT,
        identity_binding=binding,
        ttl_seconds=900,
        now=int(time.time()),
        nonce=_unique_id("nonce"),
        workflow_ref=WORKFLOW_REF,
    )


def signed_init_data(max_user_id: str, max_chat_id: str, start_param: str) -> str:
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


async def set_user_status(
    context: ContextInteractionPgContext,
    user_id: uuid.UUID,
    status: str,
) -> None:
    async with context.engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET status = :status WHERE id = :user_id"),
            {"status": status, "user_id": user_id},
        )


async def dialog_session_count(context: ContextInteractionPgContext, user_id: uuid.UUID) -> int:
    return await user_table_count(context, "dialog_sessions", user_id)


async def pending_command_count(context: ContextInteractionPgContext, user_id: uuid.UUID) -> int:
    return await user_table_count(context, "pending_commands", user_id)


async def kaiten_connection_count(context: ContextInteractionPgContext, user_id: uuid.UUID) -> int:
    return await user_table_count(context, "kaiten_connections", user_id)


async def notification_history_count(
    context: ContextInteractionPgContext,
    user_id: uuid.UUID,
) -> int:
    return await user_table_count(context, "notification_history", user_id)


async def user_table_count(
    context: ContextInteractionPgContext,
    table_name: str,
    user_id: uuid.UUID,
) -> int:
    async with context.engine.connect() as conn:
        return int(
            (
                await conn.execute(
                    text(f"SELECT count(*) FROM {table_name} WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )
            ).scalar_one()
        )


def _unique_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"
