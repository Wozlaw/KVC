"""ASGI integration checks for MAX contextual Mini App interaction."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from kvc_api.main import create_app
from kvc_api.max.mini_app import MAX_INIT_DATA_HEADER, MAX_MINI_APP_CONTEXT_HEADER
from kvc_api.max.runtime import MaxMiniAppRuntime
from kvc_application.dto import (
    ContextInteractionOption,
    ContextInteractionResult,
    ContextInteractionView,
    IdentityResolution,
)
from kvc_config import AppSettings
from kvc_integrations.max.context_signing import MiniAppContextPurpose, MiniAppContextSigner

BOT_TOKEN = "synthetic-bot-token"
CONTEXT_SECRET = "synthetic-context-secret"
MAX_USER_ID = "max-user-api"
MAX_CHAT_ID = "max-chat-api"
USER_ID = UUID("00000000-0000-0000-0000-000000000981")
BINDING_ID = UUID("00000000-0000-0000-0000-000000000982")
WORKFLOW_REF = "synthetic-choice-api"


class FakeIdentityResolver:
    async def resolve_or_onboard_private_max_user(self, input: object) -> IdentityResolution:
        return IdentityResolution(USER_ID, BINDING_ID, "ACTIVE", False, "ACTIVE")


class FakeContextResolver:
    def __init__(self) -> None:
        self.submitted: list[str] = []

    async def get_interaction(
        self,
        *,
        user_id: UUID,
        workflow_ref: str,
    ) -> ContextInteractionView:
        assert user_id == USER_ID
        assert workflow_ref == WORKFLOW_REF
        return ContextInteractionView(
            WORKFLOW_REF,
            "Выберите действие",
            "Доступен один безопасный вариант.",
            [ContextInteractionOption("accept", "Подтвердить")],
        )

    async def submit_selection(
        self,
        *,
        user_id: UUID,
        workflow_ref: str,
        option_id: str,
    ) -> ContextInteractionResult:
        assert user_id == USER_ID
        assert workflow_ref == WORKFLOW_REF
        self.submitted.append(option_id)
        return ContextInteractionResult("completed", "Принято.")

    async def cancel_interaction(
        self,
        *,
        user_id: UUID,
        workflow_ref: str,
    ) -> ContextInteractionResult:
        assert user_id == USER_ID
        assert workflow_ref == WORKFLOW_REF
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


@pytest.mark.asyncio
async def test_context_interaction_http_lifecycle() -> None:
    resolver = FakeContextResolver()
    sender = FakeSender()
    runtime = MaxMiniAppRuntime(
        identity_resolver_factory=lambda: FakeIdentityResolver(),
        kaiten_connection_binder_factory=lambda: object(),  # type: ignore[arg-type]
        message_sender=sender,
        context_signer=MiniAppContextSigner(CONTEXT_SECRET),
        context_interaction_resolver_factory=lambda: resolver,
    )
    app = create_app(_settings(), max_mini_app_runtime=runtime)
    context_ref = _context_ref()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        loaded = await client.get("/max/app/api/context", headers=_headers(context_ref))
        submitted = await client.post(
            "/max/app/api/context",
            headers=_headers(context_ref),
            json={"selected_option_id": "accept"},
        )
        cancelled = await client.post(
            "/max/app/api/context/cancel",
            headers=_headers(context_ref),
        )

    assert loaded.status_code == 200
    assert loaded.json() == {
        "title": "Выберите действие",
        "prompt": "Доступен один безопасный вариант.",
        "options": [{"id": "accept", "label": "Подтвердить", "description": None}],
        "allow_cancel": True,
    }
    assert submitted.status_code == 200
    assert submitted.json() == {"status": "completed", "confirmation_status": "sent"}
    assert cancelled.status_code == 200
    assert cancelled.json() == {"status": "cancelled", "confirmation_status": "not_required"}
    assert resolver.submitted == ["accept"]
    assert sender.calls == [(MAX_CHAT_ID, "Принято.")]


def _settings() -> AppSettings:
    return AppSettings(
        max_bot_token=SecretStr(BOT_TOKEN),
        max_mini_app_context_secret=SecretStr(CONTEXT_SECRET),
    )


def _headers(context_ref: str) -> dict[str, str]:
    return {
        MAX_INIT_DATA_HEADER: _signed_init_data(start_param=context_ref),
        MAX_MINI_APP_CONTEXT_HEADER: context_ref,
    }


def _context_ref() -> str:
    signer = MiniAppContextSigner(CONTEXT_SECRET)
    binding = signer.make_identity_binding(max_user_id=MAX_USER_ID, chat_id=MAX_CHAT_ID)
    return signer.issue(
        purpose=MiniAppContextPurpose.SYNTHETIC_CONTEXT,
        identity_binding=binding,
        ttl_seconds=900,
        now=int(time.time()),
        nonce="nonce-api",
        workflow_ref=WORKFLOW_REF,
    )


def _signed_init_data(*, start_param: str) -> str:
    params = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": MAX_USER_ID}, separators=(",", ":")),
        "chat": json.dumps({"id": MAX_CHAT_ID, "type": "dialog"}, separators=(",", ":")),
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
