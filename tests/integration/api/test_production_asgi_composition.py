"""Production ASGI composition regression tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from kvc_api.main import create_app
from kvc_api.max.mini_app import MAX_INIT_DATA_HEADER, MAX_MINI_APP_CONTEXT_HEADER
from kvc_api.max.runtime import MaxMiniAppRuntime, MaxRuntime
from kvc_api.production import ProductionConfigurationError, create_production_app
from kvc_config import AppSettings, get_settings
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
BOT_TOKEN = "synthetic-production-bot-token"
WEBHOOK_SECRET = "synthetic-production-webhook-secret"
CONTEXT_SECRET = "synthetic-production-context-secret"
KAITEN_TOKEN = "synthetic-production-kaiten-token"
BUSINESS_TABLES = (
    "dialog_sessions",
    "kaiten_connections",
    "max_chats",
    "notification_history",
    "notification_settings",
    "pending_commands",
    "users",
)


@dataclass
class ProductionPgContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    baseline_counts: dict[str, int]
    max_user_ids: list[str]
    max_requests: list[httpx.Request]
    kaiten_requests: list[httpx.Request]
    http_client: httpx.AsyncClient


@pytest_asyncio.fixture
async def live_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    if settings.app_env != "development":
        pytest.skip("production ASGI composition tests require KVC_APP_ENV=development.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip("production ASGI composition tests require the kvc_dev database.")
            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip("production ASGI composition tests require the accepted Alembic head.")

        yield engine
    finally:
        await dispose_async_engine(engine)


@pytest_asyncio.fixture
async def production_context(live_engine: AsyncEngine) -> AsyncIterator[ProductionPgContext]:
    max_requests: list[httpx.Request] = []
    kaiten_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "platform-api2.max.ru" and request.url.path == "/messages":
            max_requests.append(request)
            chat_id = request.url.params.get("chat_id")
            return httpx.Response(
                200,
                json={
                    "message": {
                        "body": {"mid": f"out-{len(max_requests)}"},
                        "recipient": {"chat_id": chat_id},
                        "timestamp": 1_700_000_001,
                    }
                },
            )
        if request.url.host == "synthetic.kaiten.test":
            kaiten_requests.append(request)
            return httpx.Response(200, json={"id": "synthetic-kaiten-user"})
        return httpx.Response(404, json={"status": "unexpected_request"})

    context = ProductionPgContext(
        engine=live_engine,
        sessionmaker=create_async_sessionmaker(live_engine),
        baseline_counts=await table_counts(live_engine),
        max_user_ids=[],
        max_requests=max_requests,
        kaiten_requests=kaiten_requests,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        yield context
    finally:
        await context.http_client.aclose()
        await cleanup_max_users(live_engine, context.max_user_ids)
        assert await table_counts(live_engine) == context.baseline_counts


def test_shell_app_reproduces_live_unavailable_webhook_defect() -> None:
    client = TestClient(
        create_app(
            AppSettings(_env_file=None, max_webhook_secret=SecretStr(WEBHOOK_SECRET)),
        )
    )

    response = client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": WEBHOOK_SECRET},
        json=private_message_update("/start", "max-user", "max-chat"),
    )

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_production_composition_fails_fast_when_required_settings_are_missing() -> None:
    with pytest.raises(ProductionConfigurationError) as caught:
        create_production_app(AppSettings(_env_file=None))

    message = str(caught.value)
    assert "KVC_DATABASE_URL" in message
    assert "KVC_MAX_BOT_TOKEN" in message
    assert BOT_TOKEN not in message
    assert WEBHOOK_SECRET not in message


@pytest.mark.asyncio
async def test_production_composed_webhook_dispatches_start_without_live_max_network(
    production_context: ProductionPgContext,
) -> None:
    max_user_id = unique_id("prod-user")
    max_chat_id = unique_id("prod-chat")
    production_context.max_user_ids.append(max_user_id)
    app = production_app(production_context)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            malformed = await client.post(
                "/max/webhook",
                headers={"X-Max-Bot-Api-Secret": WEBHOOK_SECRET},
                json={"timestamp": 1},
            )
            start = await client.post(
                "/max/webhook",
                headers={"X-Max-Bot-Api-Secret": WEBHOOK_SECRET},
                json=private_message_update("/start", max_user_id, max_chat_id),
            )

    assert malformed.status_code == 400
    assert malformed.json() == {"status": "invalid_update"}
    assert start.status_code == 200
    assert start.json() == {"status": "accepted"}
    assert len(production_context.max_requests) == 1
    sent = json.loads(production_context.max_requests[0].content)
    assert "Kaiten" in sent["text"]
    assert "Authorization" in production_context.max_requests[0].headers
    assert BOT_TOKEN not in sent["text"]
    assert await user_count(production_context, max_user_id) == 1


@pytest.mark.asyncio
async def test_production_composed_mini_app_connect_and_notifications_runtime(
    production_context: ProductionPgContext,
) -> None:
    max_user_id = unique_id("prod-user")
    max_chat_id = unique_id("prod-chat")
    production_context.max_user_ids.append(max_user_id)
    app = production_app(production_context)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            connect_shell_response = await client.post("/max/app/api/connect", json={})
            connect_context = await open_app_context(
                production_context,
                client,
                command="/connect",
                max_user_id=max_user_id,
                max_chat_id=max_chat_id,
            )
            connect_response = await client.post(
                "/max/app/api/connect",
                json={
                    "init_data": signed_init_data(
                        max_user_id=max_user_id,
                        max_chat_id=max_chat_id,
                        start_param=connect_context,
                    ),
                    "context_ref": connect_context,
                    "api_base_url": "https://synthetic.kaiten.test/api/latest",
                    "token": KAITEN_TOKEN,
                },
            )
            notifications_context = await open_app_context(
                production_context,
                client,
                command="/notifications",
                max_user_id=max_user_id,
                max_chat_id=max_chat_id,
            )
            notifications_get = await client.get(
                "/max/app/api/notifications",
                headers=mini_app_headers(max_user_id, max_chat_id, notifications_context),
            )
            notifications_post = await client.post(
                "/max/app/api/notifications",
                headers=mini_app_headers(max_user_id, max_chat_id, notifications_context),
                json={"enabled": True, "due_soon_days": 3, "timezone": "UTC"},
            )

    assert connect_shell_response.status_code == 400
    assert connect_shell_response.json() == {"status": "invalid_input"}
    assert connect_response.status_code == 200
    assert connect_response.json()["status"] == "connected"
    assert notifications_get.status_code == 200
    assert notifications_get.json() == {"enabled": False, "due_soon_days": 1, "timezone": "UTC"}
    assert notifications_post.status_code == 200
    assert notifications_post.json()["settings"] == {
        "enabled": True,
        "due_soon_days": 3,
        "timezone": "UTC",
    }
    assert len(production_context.kaiten_requests) == 1
    assert KAITEN_TOKEN not in "\n".join(
        request.url.query.decode("utf-8", errors="ignore")
        for request in production_context.kaiten_requests
    )
    assert await connection_count(production_context, max_user_id) == 1
    assert await notification_history_count(production_context, max_user_id) == 0


def test_production_app_lifespan_closes_owned_resources() -> None:
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    disposed: list[object] = []
    engine = object()

    async def dispose_engine(value: object) -> None:
        disposed.append(value)

    app = create_production_app(
        valid_settings(),
        http_client_factory=lambda: http_client,
        engine_factory=lambda _: engine,  # type: ignore[arg-type,return-value]
        sessionmaker_factory=lambda _: async_sessionmaker(),  # type: ignore[arg-type]
        engine_disposer=dispose_engine,  # type: ignore[arg-type]
        max_runtime_builder=lambda **_: MaxRuntime(  # type: ignore[arg-type]
            dispatcher=object(),  # type: ignore[arg-type]
            message_sender=object(),  # type: ignore[arg-type]
            api_client=object(),  # type: ignore[arg-type]
        ),
        max_mini_app_runtime_builder=lambda **_: MaxMiniAppRuntime(
            identity_resolver_factory=lambda: object(),  # type: ignore[arg-type]
            kaiten_connection_binder_factory=lambda: object(),  # type: ignore[arg-type]
            message_sender=object(),  # type: ignore[arg-type]
            context_signer=object(),  # type: ignore[arg-type]
        ),
    )

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

    assert http_client.is_closed is True
    assert disposed == [engine]


def production_app(context: ProductionPgContext) -> Any:
    return create_production_app(
        valid_settings(),
        http_client_factory=lambda: context.http_client,
        engine_factory=lambda _: context.engine,
        sessionmaker_factory=lambda _: context.sessionmaker,
        engine_disposer=lambda _: noop(),
    )


async def noop() -> None:
    return None


def valid_settings() -> AppSettings:
    key = Fernet.generate_key().decode("ascii")
    return AppSettings(
        _env_file=None,
        database_url=SecretStr("postgresql+asyncpg://kvc:kvc@localhost/kvc_dev"),
        token_encryption_active_version=1,
        token_encryption_keys=SecretStr(json.dumps({"1": key}, separators=(",", ":"))),
        max_bot_token=SecretStr(BOT_TOKEN),
        max_webhook_secret=SecretStr(WEBHOOK_SECRET),
        max_webhook_public_url="https://kvc.example.test/max/webhook",
        max_mini_app_public_url="https://kvc.example.test/max/app/connect",
        max_mini_app_context_secret=SecretStr(CONTEXT_SECRET),
        max_inbound_mode="webhook",
    )


def private_message_update(command: str, max_user_id: str, max_chat_id: str) -> dict[str, object]:
    return {
        "update_type": "message_created",
        "timestamp": 1_700_000_000_000,
        "message": {
            "sender": {"user_id": max_user_id},
            "recipient": {"chat_id": max_chat_id, "chat_type": "dialog"},
            "body": {"mid": unique_id("mid"), "text": command},
        },
    }


async def open_app_context(
    context: ProductionPgContext,
    client: httpx.AsyncClient,
    *,
    command: str,
    max_user_id: str,
    max_chat_id: str,
) -> str:
    response = await client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": WEBHOOK_SECRET},
        json=private_message_update(command, max_user_id, max_chat_id),
    )
    assert response.status_code == 200
    return context_from_request(context.max_requests[-1])


def context_from_request(request: httpx.Request) -> str:
    payload = json.loads(request.content)
    buttons = payload["attachments"][0]["payload"]["buttons"]
    launch_url = buttons[0][0]["web_app"]
    query = parse_qs(urlsplit(launch_url).query)
    context_values = query.get("startapp")
    assert context_values is not None
    return context_values[0]


def mini_app_headers(max_user_id: str, max_chat_id: str, context_ref: str) -> dict[str, str]:
    return {
        MAX_INIT_DATA_HEADER: signed_init_data(
            max_user_id=max_user_id,
            max_chat_id=max_chat_id,
            start_param=context_ref,
        ),
        MAX_MINI_APP_CONTEXT_HEADER: context_ref,
    }


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


async def user_count(context: ProductionPgContext, max_user_id: str) -> int:
    async with context.sessionmaker() as session:
        return len(
            (await session.execute(select(MaxChat).where(MaxChat.max_user_id == max_user_id)))
            .scalars()
            .all()
        )


async def connection_count(context: ProductionPgContext, max_user_id: str) -> int:
    async with context.sessionmaker() as session:
        user_id = (
            await session.execute(select(MaxChat.user_id).where(MaxChat.max_user_id == max_user_id))
        ).scalar_one()
        return len(
            (
                await session.execute(
                    select(KaitenConnection).where(KaitenConnection.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )


async def notification_history_count(context: ProductionPgContext, max_user_id: str) -> int:
    async with context.sessionmaker() as session:
        user_id = (
            await session.execute(select(MaxChat.user_id).where(MaxChat.max_user_id == max_user_id))
        ).scalar_one()
        return len(
            (
                await session.execute(
                    select(NotificationHistory).where(NotificationHistory.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )


def unique_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"
