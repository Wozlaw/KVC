"""Live PostgreSQL acceptance for MAX Mini App Kaiten credential onboarding."""

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
from kvc_api.max.runtime import MaxMiniAppRuntime
from kvc_application.dto import KaitenCredentialVerification
from kvc_application.services import IdentityService, KaitenConnectionService
from kvc_config import AppSettings, get_settings
from kvc_integrations.max.context_signing import MiniAppContextPurpose, MiniAppContextSigner
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
from kvc_persistence.repositories import KaitenConnectionRepository, UserRepository

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
TOKEN_A = "synthetic-mini-app-token-a"
TOKEN_B = "synthetic-mini-app-token-b"


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
        self.calls: list[dict[str, object]] = []

    async def send_text_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        notify: bool = True,
    ) -> object:
        self.calls.append({"chat_id": chat_id, "text": text, "notify": notify})
        return object()


@dataclass
class MiniAppDbContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    baseline_counts: dict[str, int]
    cipher: VersionedFernetTokenCipher
    verifier: FakeVerifier
    sender: FakeSender
    max_user_ids: list[str]

    def app(self) -> FastAPI:
        runtime = MaxMiniAppRuntime(
            identity_resolver_factory=lambda: IdentityService(self.sessionmaker),
            kaiten_connection_binder_factory=lambda: KaitenConnectionService(
                self.sessionmaker,
                self.verifier,
                self.cipher,
                UtcClock(),
            ),
            message_sender=self.sender,
            context_signer=MiniAppContextSigner(CONTEXT_SECRET),
        )
        settings = AppSettings(
            max_bot_token=SecretStr(BOT_TOKEN),
            max_mini_app_context_secret=SecretStr(CONTEXT_SECRET),
        )
        return create_app(settings, max_mini_app_runtime=runtime)


def _client(context: MiniAppDbContext) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=context.app()),
        base_url="http://testserver",
    )


@pytest_asyncio.fixture
async def live_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    if settings.app_env != "development":
        pytest.skip("MAX Mini App PostgreSQL acceptance requires KVC_APP_ENV=development.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip("MAX Mini App PostgreSQL acceptance requires the kvc_dev database.")

            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip("MAX Mini App PostgreSQL acceptance requires accepted Alembic head.")

        yield engine
    finally:
        await dispose_async_engine(engine)


@pytest_asyncio.fixture
async def db_context(live_engine: AsyncEngine) -> AsyncIterator[MiniAppDbContext]:
    key = Fernet.generate_key().decode("ascii")
    context = MiniAppDbContext(
        engine=live_engine,
        sessionmaker=create_async_sessionmaker(live_engine),
        baseline_counts=await table_counts(live_engine),
        cipher=VersionedFernetTokenCipher(keys={1: key}, active_version=1),
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
async def test_unknown_private_max_user_connects_and_plaintext_token_is_not_persisted(
    db_context: MiniAppDbContext,
) -> None:
    max_user_id = _unique_id("max-user")
    max_chat_id = _unique_id("max-chat")
    db_context.max_user_ids.append(max_user_id)
    async with _client(db_context) as client:
        response = await client.post(
            "/max/app/api/connect",
            json=_valid_body(max_user_id=max_user_id, max_chat_id=max_chat_id, token=TOKEN_A),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "connected"
    user_id = await user_id_for_max_user(db_context, max_user_id)
    connection = await connection_for_user(db_context, user_id)
    assert connection.api_base_url == API_BASE_URL
    assert connection.status == "ACTIVE"
    assert connection.kaiten_user_id == "kaiten-user-a"
    assert bytes(connection.encrypted_api_token) != TOKEN_A.encode("utf-8")
    assert TOKEN_A not in bytes(connection.encrypted_api_token).decode("utf-8", errors="ignore")
    assert (
        db_context.cipher.decrypt(
            bytes(connection.encrypted_api_token),
            connection.token_encryption_version,
        )
        == TOKEN_A
    )
    assert await token_occurrences_in_dialog_state(db_context, TOKEN_A) == 0
    assert TOKEN_A not in response.text
    assert TOKEN_A not in json.dumps(db_context.sender.calls)


@pytest.mark.asyncio
async def test_reconnect_reuses_identity_and_replaces_existing_credential(
    db_context: MiniAppDbContext,
) -> None:
    max_user_id = _unique_id("max-user")
    max_chat_id = _unique_id("max-chat")
    db_context.max_user_ids.append(max_user_id)
    first = _valid_body(max_user_id=max_user_id, max_chat_id=max_chat_id, token=TOKEN_A)
    async with _client(db_context) as client:
        assert (await client.post("/max/app/api/connect", json=first)).status_code == 200
    user_id = await user_id_for_max_user(db_context, max_user_id)
    original = await connection_for_user(db_context, user_id)
    original_id = original.id
    original_ciphertext = bytes(original.encrypted_api_token)

    db_context.verifier.verification = KaitenCredentialVerification("kaiten-user-b", "workspace-b")
    second = _valid_body(
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        token=TOKEN_B,
        purpose=MiniAppContextPurpose.RECONNECT_KAITEN,
    )
    async with _client(db_context) as client:
        response = await client.post("/max/app/api/connect", json=second)
    replaced = await connection_for_user(db_context, user_id)

    assert response.status_code == 200
    assert response.json()["mode"] == "reconnected"
    assert replaced.id == original_id
    assert bytes(replaced.encrypted_api_token) != original_ciphertext
    assert replaced.kaiten_user_id == "kaiten-user-b"
    assert replaced.workspace_id == "workspace-b"
    assert (
        db_context.cipher.decrypt(
            bytes(replaced.encrypted_api_token),
            replaced.token_encryption_version,
        )
        == TOKEN_B
    )
    assert await connection_count_for_user(db_context, user_id) == 1
    assert TOKEN_B not in response.text


@pytest.mark.asyncio
async def test_disabled_user_is_blocked_before_kaiten_verification(
    db_context: MiniAppDbContext,
) -> None:
    max_user_id = _unique_id("max-user")
    max_chat_id = _unique_id("max-chat")
    db_context.max_user_ids.append(max_user_id)
    async with _client(db_context) as client:
        assert (
            await client.post(
                "/max/app/api/connect",
                json=_valid_body(max_user_id=max_user_id, max_chat_id=max_chat_id, token=TOKEN_A),
            )
        ).status_code == 200
    user_id = await user_id_for_max_user(db_context, max_user_id)
    before = await connection_snapshot(db_context, user_id)
    await set_user_status(db_context, user_id, "DISABLED")
    verifier_calls_before = len(db_context.verifier.calls)

    async with _client(db_context) as client:
        response = await client.post(
            "/max/app/api/connect",
            json=_valid_body(
                max_user_id=max_user_id,
                max_chat_id=max_chat_id,
                token=TOKEN_B,
                purpose=MiniAppContextPurpose.RECONNECT_KAITEN,
            ),
        )

    assert response.status_code == 403
    assert response.json() == {"status": "user_disabled"}
    assert len(db_context.verifier.calls) == verifier_calls_before
    assert await connection_snapshot(db_context, user_id) == before
    assert TOKEN_B not in response.text


@pytest.mark.asyncio
async def test_wrong_context_user_produces_no_identity_or_credential_rows(
    db_context: MiniAppDbContext,
) -> None:
    max_user_id = _unique_id("max-user")
    max_chat_id = _unique_id("max-chat")
    db_context.max_user_ids.append(max_user_id)
    wrong_context = _context_ref(
        max_user_id=_unique_id("wrong-user"),
        max_chat_id=max_chat_id,
    )

    async with _client(db_context) as client:
        response = await client.post(
            "/max/app/api/connect",
            json=_valid_body(
                max_user_id=max_user_id,
                max_chat_id=max_chat_id,
                context_ref=wrong_context,
                token=TOKEN_A,
            ),
        )

    assert response.status_code == 403
    assert response.json() == {"status": "invalid_context"}
    assert await optional_user_id_for_max_user(db_context, max_user_id) is None
    assert db_context.verifier.calls == []


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


async def optional_user_id_for_max_user(
    context: MiniAppDbContext,
    max_user_id: str,
) -> uuid.UUID | None:
    async with context.sessionmaker() as session:
        return (
            await session.execute(select(MaxChat.user_id).where(MaxChat.max_user_id == max_user_id))
        ).scalar_one_or_none()


async def user_id_for_max_user(context: MiniAppDbContext, max_user_id: str) -> uuid.UUID:
    user_id = await optional_user_id_for_max_user(context, max_user_id)
    assert user_id is not None
    return user_id


async def connection_for_user(context: MiniAppDbContext, user_id: uuid.UUID) -> KaitenConnection:
    async with context.sessionmaker() as session:
        connection = await KaitenConnectionRepository(session).get_for_user(user_id)
        assert connection is not None
        return connection


async def connection_count_for_user(context: MiniAppDbContext, user_id: uuid.UUID) -> int:
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


async def connection_snapshot(context: MiniAppDbContext, user_id: uuid.UUID) -> tuple[object, ...]:
    connection = await connection_for_user(context, user_id)
    return (
        connection.id,
        connection.api_base_url,
        connection.kaiten_user_id,
        connection.workspace_id,
        bytes(connection.encrypted_api_token),
        connection.token_encryption_version,
        connection.status,
        connection.last_verified_at,
    )


async def set_user_status(context: MiniAppDbContext, user_id: uuid.UUID, status: str) -> None:
    async with context.sessionmaker() as session:
        async with session.begin():
            user = await UserRepository(session).get_by_id_for_update(user_id)
            assert user is not None
            await UserRepository(session).set_status(user, status)


async def token_occurrences_in_dialog_state(context: MiniAppDbContext, token: str) -> int:
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


def _valid_body(
    *,
    max_user_id: str,
    max_chat_id: str,
    token: str,
    purpose: MiniAppContextPurpose = MiniAppContextPurpose.CONNECT_KAITEN,
    context_ref: str | None = None,
) -> dict[str, str]:
    resolved_context_ref = context_ref or _context_ref(
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        purpose=purpose,
    )
    return {
        "init_data": _signed_init_data(
            max_user_id=max_user_id,
            max_chat_id=max_chat_id,
            start_param=resolved_context_ref,
        ),
        "context_ref": resolved_context_ref,
        "api_base_url": API_BASE_URL,
        "token": token,
    }


def _context_ref(
    *,
    max_user_id: str,
    max_chat_id: str,
    purpose: MiniAppContextPurpose = MiniAppContextPurpose.CONNECT_KAITEN,
) -> str:
    signer = MiniAppContextSigner(CONTEXT_SECRET)
    binding = signer.make_identity_binding(max_user_id=max_user_id, chat_id=max_chat_id)
    return signer.issue(
        purpose=purpose,
        identity_binding=binding,
        ttl_seconds=900,
        now=int(time.time()),
        nonce=_unique_id("nonce"),
    )


def _signed_init_data(
    *,
    max_user_id: str,
    max_chat_id: str,
    start_param: str,
) -> str:
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
