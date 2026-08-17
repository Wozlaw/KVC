"""Branch-004 full automated acceptance checks."""

from __future__ import annotations

import hashlib
import hmac
import importlib.resources
import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kvc_api.main import create_app
from kvc_api.max.dispatcher import UpdateDispatcher
from kvc_api.max.mini_app import MAX_INIT_DATA_HEADER, MAX_MINI_APP_CONTEXT_HEADER
from kvc_api.max.runtime import MaxMiniAppRuntime
from kvc_api.max.service_commands import ServiceCommandHandler
from kvc_application.dto import (
    ContextInteractionOption,
    ContextInteractionResult,
    ContextInteractionView,
    KaitenCredentialVerification,
    ResolveMaxIdentityInput,
)
from kvc_application.errors import ContextInteractionInvalidSelection
from kvc_application.services import (
    IdentityService,
    KaitenConnectionService,
    NotificationSettingsService,
)
from kvc_config import AppSettings, get_settings
from kvc_integrations.max.context_signing import MiniAppContextPurpose, MiniAppContextSigner
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
BOT_TOKEN = "synthetic-branch-004-bot-token"
CONTEXT_SECRET = "synthetic-branch-004-context-secret"
API_BASE_URL = "https://synthetic.kaiten.example/api/latest"
TOKEN_A = "synthetic-branch-004-token-a"
TOKEN_B = "synthetic-branch-004-token-b"
TOKEN_C = "synthetic-branch-004-token-c"
WEBHOOK_SECRET = "synthetic-branch-004-webhook-secret"
WORKFLOW_REF = "synthetic-choice-00409"
BUSINESS_TABLES = (
    "dialog_sessions",
    "kaiten_connections",
    "max_chats",
    "notification_history",
    "notification_settings",
    "pending_commands",
    "users",
)
STATIC_FILES = ("app.css", "app.js", "notifications.js", "context.js")
MINI_APP_PAGES = ("/max/app/connect", "/max/app/notifications", "/max/app/context")
FORBIDDEN_COMMANDS = (
    "/boards",
    "/cards",
    "/move",
    "/comment",
    "/due",
    "/nodue",
    "/attach",
    "/photos",
    "/summary",
)


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


class FakeContextResolver:
    def __init__(self) -> None:
        self.submissions: list[tuple[uuid.UUID, str, str]] = []

    async def get_interaction(
        self,
        *,
        user_id: uuid.UUID,
        workflow_ref: str,
    ) -> ContextInteractionView:
        return ContextInteractionView(
            workflow_ref,
            "Выберите вариант",
            "Доступны безопасные варианты.",
            (
                ContextInteractionOption("one", "Первый"),
                ContextInteractionOption("two", "Второй"),
            ),
        )

    async def submit_selection(
        self,
        *,
        user_id: uuid.UUID,
        workflow_ref: str,
        option_id: str,
    ) -> ContextInteractionResult:
        if option_id not in {"one", "two"}:
            raise ContextInteractionInvalidSelection("synthetic")
        self.submissions.append((user_id, workflow_ref, option_id))
        return ContextInteractionResult("completed", "Выбор принят.")

    async def cancel_interaction(
        self,
        *,
        user_id: uuid.UUID,
        workflow_ref: str,
    ) -> ContextInteractionResult:
        return ContextInteractionResult("cancelled")


@dataclass
class Branch004AcceptanceContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    baseline_counts: dict[str, int]
    cipher: VersionedFernetTokenCipher
    verifier: FakeVerifier
    sender: FakeSender
    context_resolver: FakeContextResolver
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

    def app(self, *, context_resolver_enabled: bool = True) -> FastAPI:
        runtime = MaxMiniAppRuntime(
            identity_resolver_factory=lambda: IdentityService(self.sessionmaker),
            kaiten_connection_binder_factory=self.connection_service,
            message_sender=self.sender,
            context_signer=MiniAppContextSigner(CONTEXT_SECRET),
            notification_settings_service_factory=lambda: NotificationSettingsService(
                self.sessionmaker
            ),
            context_interaction_resolver_factory=(
                (lambda: self.context_resolver) if context_resolver_enabled else None
            ),
        )
        return create_app(_settings(), max_mini_app_runtime=runtime)


@pytest_asyncio.fixture
async def live_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    if settings.app_env != "development":
        pytest.skip("Branch 004 PostgreSQL acceptance requires development env.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip("Branch 004 PostgreSQL acceptance requires kvc_dev.")
            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip("Branch 004 PostgreSQL acceptance requires accepted Alembic head.")
        yield engine
    finally:
        await dispose_async_engine(engine)


@pytest_asyncio.fixture
async def branch_context(
    live_engine: AsyncEngine,
) -> AsyncIterator[Branch004AcceptanceContext]:
    context = Branch004AcceptanceContext(
        engine=live_engine,
        sessionmaker=create_async_sessionmaker(live_engine),
        baseline_counts=await table_counts(live_engine),
        cipher=VersionedFernetTokenCipher(
            keys={1: Fernet.generate_key().decode("ascii")},
            active_version=1,
        ),
        verifier=FakeVerifier(),
        sender=FakeSender(),
        context_resolver=FakeContextResolver(),
        max_user_ids=[],
    )
    try:
        yield context
    finally:
        await cleanup_max_users(live_engine, context.max_user_ids)
        assert await table_counts(live_engine) == context.baseline_counts


@pytest.mark.asyncio
async def test_branch_004_full_lifecycle_postgresql_acceptance(
    branch_context: Branch004AcceptanceContext,
) -> None:
    max_user_id = _unique_id("max-user")
    max_chat_id = _unique_id("max-chat")
    branch_context.max_user_ids.append(max_user_id)

    await dispatch_command(branch_context, "/start", max_user_id, max_chat_id)
    await dispatch_command(branch_context, "/connection", max_user_id, max_chat_id)
    await dispatch_command(branch_context, "/connect", max_user_id, max_chat_id)
    connect_context = branch_context.sender.open_app_calls[-1][2]
    await submit_connect(
        branch_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=connect_context,
        token=TOKEN_A,
    )
    await dispatch_command(branch_context, "/connection", max_user_id, max_chat_id)
    await dispatch_command(branch_context, "/status", max_user_id, max_chat_id)

    await dispatch_command(branch_context, "/notifications", max_user_id, max_chat_id)
    notification_context = branch_context.sender.open_app_calls[-1][2]
    assert branch_context.sender.open_app_calls[-1][4] == "/max/app/notifications"
    assert await notification_get(
        branch_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=notification_context,
    ) == {"enabled": False, "due_soon_days": 1, "timezone": "UTC"}
    saved_settings = await notification_post(
        branch_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=notification_context,
        payload={"enabled": True, "due_soon_days": 3, "timezone": "Europe/Warsaw"},
    )
    assert saved_settings["status"] == "saved"
    assert saved_settings["settings"] == {
        "enabled": True,
        "due_soon_days": 3,
        "timezone": "Europe/Warsaw",
    }
    assert await notification_get(
        branch_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=notification_context,
    ) == {"enabled": True, "due_soon_days": 3, "timezone": "Europe/Warsaw"}

    branch_context.verifier.verification = KaitenCredentialVerification(
        "kaiten-user-b",
        "workspace-b",
    )
    await dispatch_command(branch_context, "/reconnect", max_user_id, max_chat_id)
    reconnect_context = branch_context.sender.open_app_calls[-1][2]
    await submit_connect(
        branch_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=reconnect_context,
        token=TOKEN_B,
    )

    await dispatch_command(branch_context, "/disable", max_user_id, max_chat_id)
    await dispatch_command(branch_context, "/connection", max_user_id, max_chat_id)

    branch_context.verifier.verification = KaitenCredentialVerification("kaiten-user-c", None)
    await dispatch_command(branch_context, "/reconnect", max_user_id, max_chat_id)
    reenable_context = branch_context.sender.open_app_calls[-1][2]
    await submit_connect(
        branch_context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=reenable_context,
        token=TOKEN_C,
    )

    user_id = await user_id_for_max_user(branch_context, max_user_id)
    connection = await connection_for_user(branch_context, user_id)
    assert connection.status == "ACTIVE"
    assert connection.kaiten_user_id == "kaiten-user-c"
    assert await connection_count_for_user(branch_context, user_id) == 1
    assert await notification_settings_count(branch_context, user_id) == 1
    assert await max_binding_count(branch_context, max_user_id) == 1
    assert await dialog_session_count(branch_context, user_id) == 0
    assert await pending_command_count(branch_context, user_id) == 0
    assert await notification_history_count(branch_context, user_id) == 0
    assert bytes(connection.encrypted_api_token) != TOKEN_C.encode("utf-8")
    assert (
        branch_context.cipher.decrypt(
            bytes(connection.encrypted_api_token),
            connection.token_encryption_version,
        )
        == TOKEN_C
    )
    assert await token_occurrences_in_dialog_state(branch_context, TOKEN_A) == 0
    assert await token_occurrences_in_dialog_state(branch_context, TOKEN_B) == 0
    assert await token_occurrences_in_dialog_state(branch_context, TOKEN_C) == 0
    rendered_sender = json.dumps(
        branch_context.sender.text_calls + branch_context.sender.open_app_calls,
        ensure_ascii=False,
    )
    assert TOKEN_A not in rendered_sender
    assert TOKEN_B not in rendered_sender
    assert TOKEN_C not in rendered_sender
    assert all(
        re.fullmatch(r"^[A-Za-z0-9_-]+$", call[2]) and len(call[2]) <= 512
        for call in branch_context.sender.open_app_calls
    )


@pytest.mark.asyncio
async def test_branch_004_rotation_cross_user_disabled_and_context_boundaries(
    branch_context: Branch004AcceptanceContext,
) -> None:
    first_user = _unique_id("max-user")
    first_chat = _unique_id("max-chat")
    second_user = _unique_id("max-user")
    second_chat = _unique_id("max-chat")
    branch_context.max_user_ids.extend([first_user, second_user])
    await onboard(branch_context, first_user, first_chat)
    await onboard(branch_context, second_user, second_chat)

    connect_context = context_ref_for(first_user, first_chat, MiniAppContextPurpose.CONNECT_KAITEN)
    reconnect_context = context_ref_for(
        first_user,
        first_chat,
        MiniAppContextPurpose.RECONNECT_KAITEN,
    )
    notification_context = context_ref_for(
        first_user,
        first_chat,
        MiniAppContextPurpose.NOTIFICATION_SETTINGS,
    )
    synthetic_context = context_ref_for(
        first_user,
        first_chat,
        MiniAppContextPurpose.SYNTHETIC_CONTEXT,
        workflow_ref=WORKFLOW_REF,
    )

    async with async_client(branch_context.app()) as client:
        responses = [
            await client.post(
                "/max/app/api/connect",
                json=connect_body(
                    second_user,
                    second_chat,
                    connect_context,
                    TOKEN_A,
                ),
            ),
            await client.post(
                "/max/app/api/connect",
                json=connect_body(
                    second_user,
                    second_chat,
                    reconnect_context,
                    TOKEN_B,
                ),
            ),
            await client.get(
                "/max/app/api/notifications",
                headers=headers(second_user, second_chat, notification_context),
            ),
            await client.get(
                "/max/app/api/context",
                headers=headers(second_user, second_chat, synthetic_context),
            ),
        ]
    assert [response.status_code for response in responses] == [403, 403, 403, 403]
    assert [response.json()["status"] for response in responses] == [
        "invalid_context",
        "invalid_context",
        "invalid_context",
        "invalid_context",
    ]
    assert branch_context.verifier.calls == []
    assert branch_context.context_resolver.submissions == []

    old_chat_context = context_ref_for(
        first_user,
        first_chat,
        MiniAppContextPurpose.NOTIFICATION_SETTINGS,
    )
    rotated_chat = _unique_id("max-chat")
    old_context_response = await notification_get_response(
        branch_context,
        max_user_id=first_user,
        max_chat_id=rotated_chat,
        context_ref=old_chat_context,
    )
    fresh_context = context_ref_for(
        first_user,
        rotated_chat,
        MiniAppContextPurpose.NOTIFICATION_SETTINGS,
    )
    fresh_response = await notification_get_response(
        branch_context,
        max_user_id=first_user,
        max_chat_id=rotated_chat,
        context_ref=fresh_context,
    )
    assert old_context_response.status_code == 403
    assert old_context_response.json() == {"status": "invalid_context"}
    assert fresh_response.status_code == 200
    assert await max_binding_count(branch_context, first_user) == 1

    user_id = await user_id_for_max_user(branch_context, first_user)
    await set_user_status(branch_context, user_id, "DISABLED")
    disabled_context = context_ref_for(
        first_user,
        rotated_chat,
        MiniAppContextPurpose.SYNTHETIC_CONTEXT,
        workflow_ref=WORKFLOW_REF,
    )
    async with async_client(branch_context.app()) as client:
        disabled_get = await client.get(
            "/max/app/api/context",
            headers=headers(first_user, rotated_chat, disabled_context),
        )
        disabled_post = await client.post(
            "/max/app/api/context",
            headers=headers(first_user, rotated_chat, disabled_context),
            json={"selected_option_id": "one"},
        )
    assert disabled_get.status_code == 403
    assert disabled_get.json() == {"status": "user_disabled"}
    assert disabled_post.status_code == 403
    assert disabled_post.json() == {"status": "user_disabled"}


def test_branch_004_route_headers_cors_and_missing_config_acceptance() -> None:
    app = create_app(_settings())
    client = TestClient(app)

    for absent_path in ("/max/app/home", "/max/app/dashboard", "/max/app/cards"):
        assert client.get(absent_path).status_code == 404
    assert client.get("/health").json() == {
        "status": "ok",
        "service": "kaiten-voice-control",
    }

    for page_path in MINI_APP_PAGES:
        response = client.get(page_path)
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'none'" in csp
        assert "connect-src 'self'" in csp
        assert "unsafe-eval" not in csp
        assert "*" not in csp
        assert "frame-ancestors" not in csp
        assert "X-Frame-Options" not in response.headers
        assert "Access-Control-Allow-Origin" not in response.headers

    no_secret_client = TestClient(
        create_app(AppSettings(_env_file=None, max_bot_token=SecretStr(BOT_TOKEN)))
    )
    context_ref = context_ref_for(
        "max-user",
        "max-chat",
        MiniAppContextPurpose.SYNTHETIC_CONTEXT,
        workflow_ref=WORKFLOW_REF,
    )
    response = no_secret_client.get(
        "/max/app/api/context",
        headers=headers("max-user", "max-chat", context_ref),
    )
    assert response.status_code == 503
    assert response.json() == {"status": "configuration_error"}


def test_branch_004_static_package_and_browser_security_inventory() -> None:
    files = {
        name: Path("src/kvc_api/max/static", name).read_text(encoding="utf-8")
        for name in STATIC_FILES
    }
    for name in STATIC_FILES:
        assert importlib.resources.files("kvc_api.max").joinpath("static", name).is_file()

    joined_static = "\n".join(files.values())
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "IndexedDB",
        "document.cookie",
        "console.",
        "eval(",
        "Authorization",
        "KVC_MAX_",
        "Fernet",
    ):
        assert forbidden not in joined_static
    assert "https://st.max.ru/js/max-web-app.js" not in joined_static
    assert 'fetch("/max/app/api/connect"' in files["app.js"]
    assert 'fetch("/max/app/api/notifications"' in files["notifications.js"]
    assert 'fetch("/max/app/api/context"' in files["context.js"]
    assert "textContent" in files["context.js"]
    assert "createElement" in files["context.js"]
    assert "innerHTML" not in files["context.js"]
    assert "insertAdjacentHTML" not in files["context.js"]


def test_branch_004_source_scope_purity_and_retry_inventory() -> None:
    branch_files = _branch_files()
    assert not any(
        path.startswith("src/kvc_persistence/migrations/versions/") for path in branch_files
    )
    assert "src/kvc_domain/__init__.py" not in branch_files
    assert "package-lock.json" not in branch_files
    assert not any(path.startswith("frontend/") for path in branch_files)
    assert not any(path.endswith((".tsx", ".jsx", ".vue")) for path in branch_files)

    application_source = _read_tree("src/kvc_application")
    domain_source = _read_tree("src/kvc_domain")
    for forbidden in ("fastapi", "httpx", "kvc_integrations.max", "WebApp", "Bridge"):
        assert forbidden not in application_source
        assert forbidden not in domain_source

    api_max_business_source = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "src/kvc_api/max/dispatcher.py",
            "src/kvc_api/max/mini_app.py",
            "src/kvc_api/max/routes.py",
            "src/kvc_api/max/service_commands.py",
            "src/kvc_api/max/webhook.py",
        )
    )
    assert "Authorization" not in api_max_business_source
    assert "KaitenHttpCredentialVerifier" not in api_max_business_source
    assert "KaitenConnectionRepository" not in api_max_business_source
    assert "PendingCommandRepository" not in api_max_business_source
    assert "context-demo" not in api_max_business_source
    assert "debug-context" not in api_max_business_source
    assert "/synthetic" not in api_max_business_source

    max_runtime_source = _read_tree("src/kvc_api/max") + _read_tree("src/kvc_integrations/max")
    assert "tenacity" not in max_runtime_source
    assert "while True" not in _read_tree("src/kvc_api/max")
    assert "asyncio.sleep" not in _read_tree("src/kvc_api/max")
    assert "asyncio.sleep" in Path("src/kvc_integrations/max/long_polling.py").read_text(
        encoding="utf-8"
    )


def test_branch_004_command_inventory_and_zoneinfo_acceptance() -> None:
    help_text = Path("src/kvc_api/max/response_text.py").read_text(encoding="utf-8")
    for command in (
        "/connect",
        "/reconnect",
        "/connection",
        "/status",
        "/notifications",
        "/disable",
        "/help",
    ):
        assert command in help_text
    for command in FORBIDDEN_COMMANDS:
        assert command not in help_text

    available = []
    unavailable = []
    for zone_name in ("UTC", "Europe/Warsaw", "Europe/Moscow", "Asia/Tokyo"):
        try:
            ZoneInfo(zone_name)
        except ZoneInfoNotFoundError:
            unavailable.append(zone_name)
        else:
            available.append(zone_name)
    assert set(available + unavailable) == {"UTC", "Europe/Warsaw", "Europe/Moscow", "Asia/Tokyo"}
    assert "UTC" in available or "UTC" in unavailable


def _settings() -> AppSettings:
    return AppSettings(
        max_bot_token=SecretStr(BOT_TOKEN),
        max_webhook_secret=SecretStr(WEBHOOK_SECRET),
        max_mini_app_context_secret=SecretStr(CONTEXT_SECRET),
    )


async def dispatch_command(
    context: Branch004AcceptanceContext,
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
            message_id=_unique_id("mid"),
            message_text=command,
            message_timestamp=2,
            callback_payload=None,
        )
    )
    assert outcome.response_sent is True


async def onboard(
    context: Branch004AcceptanceContext,
    max_user_id: str,
    max_chat_id: str,
) -> uuid.UUID:
    identity = await IdentityService(context.sessionmaker).resolve_or_onboard_private_max_user(
        ResolveMaxIdentityInput(max_user_id, max_chat_id, "PRIVATE")
    )
    return identity.user_id


async def submit_connect(
    context: Branch004AcceptanceContext,
    *,
    max_user_id: str,
    max_chat_id: str,
    context_ref: str,
    token: str,
) -> dict[str, object]:
    async with async_client(context.app()) as client:
        response = await client.post(
            "/max/app/api/connect",
            json=connect_body(max_user_id, max_chat_id, context_ref, token),
        )
    assert response.status_code == 200
    return dict(response.json())


async def notification_get(
    context: Branch004AcceptanceContext,
    *,
    max_user_id: str,
    max_chat_id: str,
    context_ref: str,
) -> dict[str, object]:
    response = await notification_get_response(
        context,
        max_user_id=max_user_id,
        max_chat_id=max_chat_id,
        context_ref=context_ref,
    )
    assert response.status_code == 200
    return dict(response.json())


async def notification_get_response(
    context: Branch004AcceptanceContext,
    *,
    max_user_id: str,
    max_chat_id: str,
    context_ref: str,
) -> httpx.Response:
    async with async_client(context.app()) as client:
        return await client.get(
            "/max/app/api/notifications",
            headers=headers(max_user_id, max_chat_id, context_ref),
        )


async def notification_post(
    context: Branch004AcceptanceContext,
    *,
    max_user_id: str,
    max_chat_id: str,
    context_ref: str,
    payload: dict[str, object],
) -> dict[str, object]:
    async with async_client(context.app()) as client:
        response = await client.post(
            "/max/app/api/notifications",
            headers=headers(max_user_id, max_chat_id, context_ref),
            json=payload,
        )
    assert response.status_code == 200
    return dict(response.json())


def async_client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    )


def connect_body(
    max_user_id: str,
    max_chat_id: str,
    context_ref: str,
    token: str,
) -> dict[str, str]:
    return {
        "init_data": signed_init_data(max_user_id, max_chat_id, context_ref),
        "context_ref": context_ref,
        "api_base_url": API_BASE_URL,
        "token": token,
    }


def headers(max_user_id: str, max_chat_id: str, context_ref: str) -> dict[str, str]:
    return {
        MAX_INIT_DATA_HEADER: signed_init_data(max_user_id, max_chat_id, context_ref),
        MAX_MINI_APP_CONTEXT_HEADER: context_ref,
    }


def context_ref_for(
    max_user_id: str,
    max_chat_id: str,
    purpose: MiniAppContextPurpose,
    *,
    workflow_ref: str | None = None,
) -> str:
    signer = MiniAppContextSigner(CONTEXT_SECRET)
    binding = signer.make_identity_binding(max_user_id=max_user_id, chat_id=max_chat_id)
    return signer.issue(
        purpose=purpose,
        identity_binding=binding,
        ttl_seconds=900,
        now=int(time.time()),
        nonce=_unique_id("nonce"),
        workflow_ref=workflow_ref,
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


async def user_id_for_max_user(
    context: Branch004AcceptanceContext,
    max_user_id: str,
) -> uuid.UUID:
    async with context.sessionmaker() as session:
        user_id = (
            await session.execute(select(MaxChat.user_id).where(MaxChat.max_user_id == max_user_id))
        ).scalar_one_or_none()
        assert user_id is not None
        return user_id


async def connection_for_user(
    context: Branch004AcceptanceContext,
    user_id: uuid.UUID,
) -> KaitenConnection:
    async with context.sessionmaker() as session:
        connection = await KaitenConnectionRepository(session).get_for_user(user_id)
        assert connection is not None
        return connection


async def connection_count_for_user(
    context: Branch004AcceptanceContext,
    user_id: uuid.UUID,
) -> int:
    return await user_table_count(context, "kaiten_connections", user_id)


async def notification_settings_count(
    context: Branch004AcceptanceContext,
    user_id: uuid.UUID,
) -> int:
    return await user_table_count(context, "notification_settings", user_id)


async def dialog_session_count(context: Branch004AcceptanceContext, user_id: uuid.UUID) -> int:
    return await user_table_count(context, "dialog_sessions", user_id)


async def pending_command_count(context: Branch004AcceptanceContext, user_id: uuid.UUID) -> int:
    return await user_table_count(context, "pending_commands", user_id)


async def notification_history_count(
    context: Branch004AcceptanceContext,
    user_id: uuid.UUID,
) -> int:
    return await user_table_count(context, "notification_history", user_id)


async def user_table_count(
    context: Branch004AcceptanceContext,
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


async def max_binding_count(context: Branch004AcceptanceContext, max_user_id: str) -> int:
    async with context.sessionmaker() as session:
        return len(
            (await session.execute(select(MaxChat).where(MaxChat.max_user_id == max_user_id)))
            .scalars()
            .all()
        )


async def token_occurrences_in_dialog_state(
    context: Branch004AcceptanceContext,
    token: str,
) -> int:
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


async def set_user_status(
    context: Branch004AcceptanceContext,
    user_id: uuid.UUID,
    status: str,
) -> None:
    async with context.engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET status = :status WHERE id = :user_id"),
            {"status": status, "user_id": user_id},
        )


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


def _branch_files() -> set[str]:
    output = _git_output("git diff --name-only 421a15db7a58db5836426190b205903091463b51..HEAD")
    return set(output.splitlines())


def _read_tree(root: str) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path(root).rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _git_output(command: str) -> str:
    import subprocess

    result = subprocess.run(
        command.split(),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _unique_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"
