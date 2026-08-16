"""Live PostgreSQL acceptance for final MAX service-command onboarding UX."""

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
from cryptography.fernet import Fernet
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kvc_api.main import create_app
from kvc_api.max.dispatcher import UpdateDispatcher
from kvc_api.max.runtime import MaxMiniAppRuntime
from kvc_api.max.service_commands import ServiceCommandHandler
from kvc_application.dto import KaitenCredentialVerification
from kvc_application.services import IdentityService, KaitenConnectionService
from kvc_config import AppSettings, get_settings
from kvc_integrations.max.context_signing import MiniAppContextSigner
from kvc_integrations.max.dto import MaxIncomingUpdate, MaxSentMessage
from kvc_integrations.security import VersionedFernetTokenCipher
from kvc_integrations.system.clock import UtcClock
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
from kvc_persistence.repositories import KaitenConnectionRepository

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
BOT_TOKEN = "synthetic-bot-token"
CONTEXT_SECRET = "synthetic-context-secret"
API_BASE_URL = "https://synthetic.kaiten.example/api/latest"
TOKEN_A = "synthetic-command-token-a"
TOKEN_B = "synthetic-command-token-b"
TOKEN_C = "synthetic-command-token-c"


class FakeVerifier:
    def __init__(self) -> None:
        self.verification = KaitenCredentialVerification("kaiten-user-a", None)
        self.calls: list[tuple[str, str]] = []

    async def verify(
        self,
        *,
        api_base_url: str,
        plaintext_token: str,
    ) -> KaitenCredentialVerification:
        self.calls.append((api_base_url, plaintext_token))
        return self.verification


class FakeSender:
    def __init__(self) -> None:
        self.text_calls: list[tuple[str, str]] = []
        self.open_app_calls: list[tuple[str, str, str, str]] = []

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
        format: None = None,
        notify: bool = True,
    ) -> MaxSentMessage:
        self.open_app_calls.append((chat_id, text, context_ref, label))
        return MaxSentMessage(message_id="mid-out", chat_id=chat_id, timestamp=3)


@dataclass
class CommandPgContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    baseline_counts: dict[str, int]
    cipher: VersionedFernetTokenCipher
    verifier: FakeVerifier
    sender: FakeSender
    max_user_ids: list[str]

    def connection_service(self) -> KaitenConnectionService:
        return KaitenConnectionService(
            self.sessionmaker,
            self.verifier,
            self.cipher,
            UtcClock(),
        )

    def dispatcher(self) -> UpdateDispatcher:
        return UpdateDispatcher(
            identity_resolver_factory=lambda: IdentityService(self.sessionmaker),
            message_sender=self.sender,
            service_command_handler=ServiceCommandHandler(
                context_signer=MiniAppContextSigner(CONTEXT_SECRET),
                kaiten_connection_service_factory=self.connection_service,
                mini_app_launch_enabled=True,
                now=lambda: int(time.time()),
            ),
            allowed_update_types=("message_created", "message_callback", "bot_started"),
        )

    def app(self) -> FastAPI:
        runtime = MaxMiniAppRuntime(
            identity_resolver_factory=lambda: IdentityService(self.sessionmaker),
            kaiten_connection_binder_factory=self.connection_service,
            message_sender=self.sender,
            context_signer=MiniAppContextSigner(CONTEXT_SECRET),
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
        pytest.skip("MAX service command PostgreSQL acceptance requires KVC_APP_ENV=development.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip("MAX service command PostgreSQL acceptance requires kvc_dev.")

            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip("MAX service command PostgreSQL acceptance requires accepted head.")

        yield engine
    finally:
        await dispose_async_engine(engine)


@pytest_asyncio.fixture
async def command_context(live_engine: AsyncEngine) -> AsyncIterator[CommandPgContext]:
    context = CommandPgContext(
        engine=live_engine,
        sessionmaker=create_async_sessionmaker(live_engine),
        baseline_counts=await table_counts(live_engine),
        cipher=VersionedFernetTokenCipher(
            keys={1: Fernet.generate_key().decode("ascii")},
            active_version=1,
        ),
        verifier=FakeVerifier(),
        sender=FakeSender(),
        max_user_ids=[],
    )
    try:
        yield context
    finally:
        await cleanup_max_users(live_engine, context.max_user_ids)
        assert await table_counts(live_engine) == context.baseline_counts


@pytest.mark.asyncio
async def test_full_conversational_connection_lifecycle(
    command_context: CommandPgContext,
) -> None:
    max_user_id = _unique_id("max-user")
    max_chat_id = _unique_id("max-chat")
    command_context.max_user_ids.append(max_user_id)

    await dispatch_command(
        command_context, "/start", max_user_id=max_user_id, max_chat_id=max_chat_id
    )
    await dispatch_command(
        command_context,
        "/connection",
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
    )
    await dispatch_command(
        command_context,
        "/connect",
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
    )
    connect_context = command_context.sender.open_app_calls[-1][2]
    await submit_mini_app(
        command_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=connect_context,
        token=TOKEN_A,
    )
    await dispatch_command(
        command_context,
        "/connection",
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
    )
    await dispatch_command(
        command_context, "/status", max_user_id=max_user_id, max_chat_id=max_chat_id
    )

    command_context.verifier.verification = KaitenCredentialVerification(
        "kaiten-user-b",
        "workspace-b",
    )
    await dispatch_command(
        command_context,
        "/reconnect",
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
    )
    reconnect_context = command_context.sender.open_app_calls[-1][2]
    await submit_mini_app(
        command_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=reconnect_context,
        token=TOKEN_B,
    )
    await dispatch_command(
        command_context, "/disable", max_user_id=max_user_id, max_chat_id=max_chat_id
    )
    await dispatch_command(
        command_context,
        "/connection",
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
    )

    command_context.verifier.verification = KaitenCredentialVerification("kaiten-user-c", None)
    await dispatch_command(
        command_context,
        "/reconnect",
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
    )
    reenable_context = command_context.sender.open_app_calls[-1][2]
    await submit_mini_app(
        command_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=reenable_context,
        token=TOKEN_C,
    )

    user_id = await user_id_for_max_user(command_context, max_user_id)
    connection = await connection_for_user(command_context, user_id)
    assert connection.status == "ACTIVE"
    assert connection.kaiten_user_id == "kaiten-user-c"
    assert await connection_count_for_user(command_context, user_id) == 1
    assert await max_binding_count(command_context, max_user_id) == 1
    assert await notification_settings_count(command_context, user_id) == 1
    assert (
        command_context.cipher.decrypt(
            bytes(connection.encrypted_api_token),
            connection.token_encryption_version,
        )
        == TOKEN_C
    )
    assert await token_occurrences_in_dialog_state(command_context, TOKEN_A) == 0
    assert await token_occurrences_in_dialog_state(command_context, TOKEN_B) == 0
    assert await token_occurrences_in_dialog_state(command_context, TOKEN_C) == 0
    rendered_chat = json.dumps(
        command_context.sender.text_calls + command_context.sender.open_app_calls
    )
    assert TOKEN_A not in rendered_chat
    assert TOKEN_B not in rendered_chat
    assert TOKEN_C not in rendered_chat
    assert all(
        "." not in call[2] and len(call[2]) <= 512 for call in command_context.sender.open_app_calls
    )
    assert any("Kaiten не подключён" in text for _, text in command_context.sender.text_calls)
    assert any("Kaiten подключён" in text for _, text in command_context.sender.text_calls)
    assert any(
        "Подключение Kaiten отключено" in text for _, text in command_context.sender.text_calls
    )


async def dispatch_command(
    context: CommandPgContext,
    command: str,
    *,
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


async def submit_mini_app(
    context: CommandPgContext,
    *,
    max_user_id: str,
    max_chat_id: str,
    context_ref: str,
    token: str,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=context.app()),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/max/app/api/connect",
            json={
                "init_data": signed_init_data(
                    max_user_id=max_user_id,
                    max_chat_id=max_chat_id,
                    start_param=context_ref,
                ),
                "context_ref": context_ref,
                "api_base_url": API_BASE_URL,
                "token": token,
            },
        )
    assert response.status_code == 200


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


async def user_id_for_max_user(context: CommandPgContext, max_user_id: str) -> uuid.UUID:
    async with context.sessionmaker() as session:
        user_id = (
            await session.execute(select(MaxChat.user_id).where(MaxChat.max_user_id == max_user_id))
        ).scalar_one_or_none()
        assert user_id is not None
        return user_id


async def connection_for_user(context: CommandPgContext, user_id: uuid.UUID) -> KaitenConnection:
    async with context.sessionmaker() as session:
        connection = await KaitenConnectionRepository(session).get_for_user(user_id)
        assert connection is not None
        return connection


async def connection_count_for_user(context: CommandPgContext, user_id: uuid.UUID) -> int:
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


async def max_binding_count(context: CommandPgContext, max_user_id: str) -> int:
    async with context.sessionmaker() as session:
        return len(
            (await session.execute(select(MaxChat).where(MaxChat.max_user_id == max_user_id)))
            .scalars()
            .all()
        )


async def notification_settings_count(context: CommandPgContext, user_id: uuid.UUID) -> int:
    async with context.sessionmaker() as session:
        row = (
            await session.execute(
                select(NotificationSetting).where(NotificationSetting.user_id == user_id)
            )
        ).scalar_one_or_none()
        return 0 if row is None else 1


async def token_occurrences_in_dialog_state(context: CommandPgContext, token: str) -> int:
    async with context.engine.connect() as conn:
        dialog_count = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM dialog_sessions "
                    "WHERE previous_user_message = :token "
                    "OR previous_bot_message = :token "
                    "OR current_card_title = :token "
                    "OR last_card_list::text LIKE :pattern"
                ),
                {"token": token, "pattern": f"%{token}%"},
            )
        ).scalar_one()
        command_count = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM pending_commands "
                    "WHERE original_message = :token "
                    "OR failure_reason = :token "
                    "OR arguments::text LIKE :pattern "
                    "OR unresolved_entity::text LIKE :pattern "
                    "OR candidates::text LIKE :pattern"
                ),
                {"token": token, "pattern": f"%{token}%"},
            )
        ).scalar_one()
        return int(dialog_count + command_count)


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
