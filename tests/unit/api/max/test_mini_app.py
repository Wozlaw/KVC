"""MAX Mini App credential onboarding route tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from kvc_api.main import create_app
from kvc_api.max.runtime import MaxMiniAppRuntime
from kvc_application.dto import (
    BindKaitenConnectionInput,
    IdentityResolution,
    KaitenConnectionResult,
)
from kvc_application.errors import (
    CredentialEncryptionFailed,
    IdentityConflict,
    KaitenAuthenticationFailed,
    KaitenTemporarilyUnavailable,
    KaitenVerificationFailed,
    PersistenceConflict,
    UserDisabled,
)
from kvc_config import AppSettings
from kvc_integrations.max.context_signing import MiniAppContextPurpose, MiniAppContextSigner
from kvc_integrations.max.errors import MaxApiTemporaryError

BOT_TOKEN = "synthetic-bot-token"
CONTEXT_SECRET = "synthetic-context-secret"
MAX_USER_ID = "max-user-123"
MAX_CHAT_ID = "max-chat-456"
USER_ID = UUID("00000000-0000-0000-0000-000000000301")
BINDING_ID = UUID("00000000-0000-0000-0000-000000000302")
CONNECTION_ID = UUID("00000000-0000-0000-0000-000000000303")
TOKEN = "SYNTHETIC-KAITEN-TOKEN-MUST-NOT-LEAK"
API_BASE_URL = "https://synthetic.kaiten.example/api/latest"


class FakeIdentityResolver:
    def __init__(
        self,
        resolution: IdentityResolution | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.resolution = resolution or IdentityResolution(
            user_id=USER_ID,
            max_chat_binding_id=BINDING_ID,
            user_status="ACTIVE",
            is_new_user=False,
            kaiten_connection_status=None,
        )
        self.exc = exc
        self.calls: list[object] = []

    async def resolve_or_onboard_private_max_user(self, input: object) -> IdentityResolution:
        self.calls.append(input)
        if self.exc is not None:
            raise self.exc
        return self.resolution


class FakeKaitenBinder:
    def __init__(
        self,
        result: KaitenConnectionResult | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.result = result or KaitenConnectionResult(
            connection_id=CONNECTION_ID,
            user_id=USER_ID,
            status="ACTIVE",
            api_base_url=API_BASE_URL,
            kaiten_user_id="kaiten-user",
            workspace_id=None,
            last_verified_at=datetime(2026, 8, 16, 12, tzinfo=UTC),
        )
        self.exc = exc
        self.calls: list[BindKaitenConnectionInput] = []

    async def bind_or_replace_connection(
        self,
        input: BindKaitenConnectionInput,
    ) -> KaitenConnectionResult:
        self.calls.append(input)
        if self.exc is not None:
            raise self.exc
        return self.result


class FakeSender:
    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc
        self.calls: list[dict[str, object]] = []

    async def send_text_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        notify: bool = True,
    ) -> object:
        self.calls.append({"chat_id": chat_id, "text": text, "notify": notify})
        if self.exc is not None:
            raise self.exc
        return object()


def test_connect_page_serves_max_bridge_local_assets_and_safe_headers() -> None:
    client = TestClient(create_app(_settings()))

    response = client.get("/max/app/connect")

    assert response.status_code == 200
    assert "https://st.max.ru/js/max-web-app.js" in response.text
    assert "/max/app/static/app.css" in response.text
    assert "/max/app/static/app.js" in response.text
    assert "initDataUnsafe" not in response.text
    assert "token=" not in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors" not in response.headers["Content-Security-Policy"]
    assert "X-Frame-Options" not in response.headers


def test_static_assets_are_bounded_and_do_not_store_secrets() -> None:
    client = TestClient(create_app(_settings()))

    script = client.get("/max/app/static/app.js")
    style = client.get("/max/app/static/app.css")
    traversal = client.get("/max/app/static/../mini_app.py")

    assert script.status_code == 200
    assert style.status_code == 200
    assert traversal.status_code == 404
    assert script.headers["Cache-Control"] == "no-cache"
    assert style.headers["X-Content-Type-Options"] == "nosniff"


def test_browser_script_contract_keeps_token_and_init_data_transient() -> None:
    script = Path("src/kvc_api/max/static/app.js").read_text(encoding="utf-8")

    assert "/max/app/api/connect" in script
    assert 'credentials: "same-origin"' in script
    assert "initDataUnsafe" not in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "console." not in script
    assert "clearToken()" in script
    assert "api_base_url" in script


def test_post_connect_validates_trust_boundary_binds_and_confirms() -> None:
    identity = FakeIdentityResolver()
    binder = FakeKaitenBinder()
    sender = FakeSender()
    client = _client(identity=identity, binder=binder, sender=sender)

    response = client.post("/max/app/api/connect", json=_valid_body())

    assert response.status_code == 200
    assert response.json() == {
        "status": "connected",
        "mode": "connected",
        "connection_status": "ACTIVE",
        "confirmation_status": "sent",
    }
    assert len(identity.calls) == 1
    assert binder.calls == [
        BindKaitenConnectionInput(
            user_id=USER_ID,
            api_base_url=API_BASE_URL,
            plaintext_token=TOKEN,
        )
    ]
    assert sender.calls == [
        {"chat_id": MAX_CHAT_ID, "text": "Kaiten подключен. Можно вернуться в чат.", "notify": True}
    ]
    assert TOKEN not in response.text


def test_post_connect_accepts_reconnect_purpose_without_changing_service_contract() -> None:
    binder = FakeKaitenBinder()
    client = _client(binder=binder)

    response = client.post(
        "/max/app/api/connect",
        json=_valid_body(purpose=MiniAppContextPurpose.RECONNECT_KAITEN),
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "reconnected"
    assert binder.calls[0].api_base_url == API_BASE_URL


@pytest.mark.parametrize(
    ("body_patch", "expected_status", "expected_body"),
    [
        ({"init_data": "bad-init-data"}, 403, {"status": "invalid_launch"}),
        ({"context_ref": "bad.context"}, 403, {"status": "invalid_context"}),
        ({"api_base_url": "http://synthetic.kaiten.example"}, 400, {"status": "invalid_input"}),
        ({"api_base_url": "https://127.0.0.1/api/latest"}, 400, {"status": "invalid_input"}),
        (
            {"api_base_url": "https://user:pass@example.com/api/latest"},
            400,
            {"status": "invalid_input"},
        ),
        (
            {"api_base_url": "https://example.com/api/latest?token=x"},
            400,
            {"status": "invalid_input"},
        ),
        ({"token": ""}, 400, {"status": "invalid_input"}),
    ],
)
def test_post_connect_rejects_untrusted_or_unsafe_input_before_services(
    body_patch: dict[str, str],
    expected_status: int,
    expected_body: dict[str, str],
) -> None:
    identity = FakeIdentityResolver()
    binder = FakeKaitenBinder()
    client = _client(identity=identity, binder=binder)
    body = _valid_body()
    body.update(body_patch)

    response = client.post("/max/app/api/connect", json=body)

    assert response.status_code == expected_status
    assert response.json() == expected_body
    assert identity.calls == []
    assert binder.calls == []
    assert TOKEN not in response.text


def test_post_connect_rejects_expired_init_data_without_echoing_payload() -> None:
    client = _client()
    expired_init_data = _signed_init_data(auth_date=int(time.time()) - 901)

    response = client.post(
        "/max/app/api/connect",
        json=_valid_body(init_data=expired_init_data),
    )

    assert response.status_code == 409
    assert response.json() == {"status": "expired_launch"}
    assert expired_init_data not in response.text


def test_post_connect_rejects_non_private_launch() -> None:
    client = _client()

    response = client.post(
        "/max/app/api/connect",
        json=_valid_body(chat_type="chat"),
    )

    assert response.status_code == 403
    assert response.json() == {"status": "private_chat_required"}


def test_post_connect_rejects_context_for_wrong_user_or_chat() -> None:
    identity = FakeIdentityResolver()
    binder = FakeKaitenBinder()
    client = _client(identity=identity, binder=binder)
    wrong_context = _context_ref(max_user_id="other-user", chat_id=MAX_CHAT_ID)

    response = client.post(
        "/max/app/api/connect",
        json=_valid_body(context_ref=wrong_context),
    )

    assert response.status_code == 403
    assert response.json() == {"status": "invalid_context"}
    assert identity.calls == []
    assert binder.calls == []


def test_post_connect_rejects_notification_context_purpose() -> None:
    client = _client()

    response = client.post(
        "/max/app/api/connect",
        json=_valid_body(purpose=MiniAppContextPurpose.NOTIFICATION_SETTINGS),
    )

    assert response.status_code == 403
    assert response.json() == {"status": "invalid_context"}


def test_post_connect_rejects_expired_context() -> None:
    signer = MiniAppContextSigner(CONTEXT_SECRET)
    binding = signer.make_identity_binding(max_user_id=MAX_USER_ID, chat_id=MAX_CHAT_ID)
    context_ref = signer.issue(
        purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        identity_binding=binding,
        ttl_seconds=1,
        now=int(time.time()) - 2,
        nonce="expired",
    )
    client = _client()

    response = client.post(
        "/max/app/api/connect",
        json=_valid_body(context_ref=context_ref),
    )

    assert response.status_code == 409
    assert response.json() == {"status": "expired_context"}


@pytest.mark.parametrize(
    ("identity_exc", "resolution", "expected_status", "expected_body"),
    [
        (IdentityConflict("synthetic"), None, 409, {"status": "identity_conflict"}),
        (PersistenceConflict("synthetic"), None, 503, {"status": "temporary_failure"}),
        (
            None,
            IdentityResolution(
                user_id=USER_ID,
                max_chat_binding_id=BINDING_ID,
                user_status="DISABLED",
                is_new_user=False,
                kaiten_connection_status=None,
            ),
            403,
            {"status": "user_disabled"},
        ),
    ],
)
def test_post_connect_maps_identity_failures_before_kaiten_verification(
    identity_exc: Exception | None,
    resolution: IdentityResolution | None,
    expected_status: int,
    expected_body: dict[str, str],
) -> None:
    identity = FakeIdentityResolver(resolution=resolution, exc=identity_exc)
    binder = FakeKaitenBinder()
    client = _client(identity=identity, binder=binder)

    response = client.post("/max/app/api/connect", json=_valid_body())

    assert response.status_code == expected_status
    assert response.json() == expected_body
    assert binder.calls == []
    assert TOKEN not in response.text


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_body"),
    [
        (UserDisabled("synthetic"), 403, {"status": "user_disabled"}),
        (KaitenAuthenticationFailed("synthetic"), 400, {"status": "kaiten_auth_failed"}),
        (KaitenTemporarilyUnavailable("synthetic"), 503, {"status": "kaiten_unavailable"}),
        (KaitenVerificationFailed("synthetic"), 502, {"status": "kaiten_verification_failed"}),
        (CredentialEncryptionFailed("synthetic"), 500, {"status": "secure_store_failed"}),
        (PersistenceConflict("synthetic"), 503, {"status": "temporary_failure"}),
    ],
)
def test_post_connect_maps_kaiten_service_errors_without_token_echo(
    exc: Exception,
    expected_status: int,
    expected_body: dict[str, str],
) -> None:
    binder = FakeKaitenBinder(exc=exc)
    sender = FakeSender()
    client = _client(binder=binder, sender=sender)

    response = client.post("/max/app/api/connect", json=_valid_body())

    assert response.status_code == expected_status
    assert response.json() == expected_body
    assert TOKEN not in response.text
    assert sender.calls == []


def test_confirmation_failure_does_not_rollback_success_or_retry() -> None:
    sender = FakeSender(exc=MaxApiTemporaryError("synthetic temporary failure"))
    binder = FakeKaitenBinder()
    client = _client(binder=binder, sender=sender)

    response = client.post("/max/app/api/connect", json=_valid_body())

    assert response.status_code == 200
    assert response.json()["confirmation_status"] == "failed"
    assert len(binder.calls) == 1
    assert len(sender.calls) == 1
    assert TOKEN not in json.dumps(sender.calls)


def test_post_without_runtime_or_required_secrets_is_unavailable_without_leak() -> None:
    client_without_runtime = TestClient(create_app(_settings()))
    client_without_secrets = TestClient(create_app(AppSettings()))

    first = client_without_runtime.post("/max/app/api/connect", json=_valid_body())
    second = client_without_secrets.post("/max/app/api/connect", json=_valid_body())

    assert first.status_code == 503
    assert first.json() == {"status": "unavailable"}
    assert second.status_code == 503
    assert second.json() == {"status": "configuration_error"}
    assert TOKEN not in first.text
    assert TOKEN not in second.text


def _client(
    *,
    identity: FakeIdentityResolver | None = None,
    binder: FakeKaitenBinder | None = None,
    sender: FakeSender | None = None,
) -> TestClient:
    runtime = MaxMiniAppRuntime(
        identity_resolver_factory=lambda: identity or FakeIdentityResolver(),
        kaiten_connection_binder_factory=lambda: binder or FakeKaitenBinder(),
        message_sender=sender or FakeSender(),
        context_signer=MiniAppContextSigner(CONTEXT_SECRET),
    )
    return TestClient(create_app(_settings(), max_mini_app_runtime=runtime))


def _settings() -> AppSettings:
    return AppSettings(
        max_bot_token=SecretStr(BOT_TOKEN),
        max_mini_app_context_secret=SecretStr(CONTEXT_SECRET),
    )


def _valid_body(
    *,
    init_data: str | None = None,
    context_ref: str | None = None,
    purpose: MiniAppContextPurpose = MiniAppContextPurpose.CONNECT_KAITEN,
    chat_type: str = "dialog",
) -> dict[str, str]:
    resolved_context_ref = context_ref or _context_ref(purpose=purpose)
    return {
        "init_data": init_data
        or _signed_init_data(start_param=resolved_context_ref, chat_type=chat_type),
        "context_ref": resolved_context_ref,
        "api_base_url": API_BASE_URL,
        "token": TOKEN,
    }


def _context_ref(
    *,
    purpose: MiniAppContextPurpose = MiniAppContextPurpose.CONNECT_KAITEN,
    max_user_id: str = MAX_USER_ID,
    chat_id: str = MAX_CHAT_ID,
) -> str:
    signer = MiniAppContextSigner(CONTEXT_SECRET)
    binding = signer.make_identity_binding(max_user_id=max_user_id, chat_id=chat_id)
    return signer.issue(
        purpose=purpose,
        identity_binding=binding,
        ttl_seconds=900,
        now=int(time.time()),
        nonce=f"nonce-{purpose.value}",
    )


def _signed_init_data(
    *,
    auth_date: int | None = None,
    start_param: str | None = None,
    chat_type: str = "dialog",
    bot_token: str = BOT_TOKEN,
) -> str:
    params: dict[str, str] = {
        "auth_date": str(auth_date or int(time.time())),
        "user": json.dumps({"id": MAX_USER_ID}, separators=(",", ":")),
        "chat": json.dumps({"id": MAX_CHAT_ID, "type": chat_type}, separators=(",", ":")),
    }
    if start_param is not None:
        params["start_param"] = start_param
    data_check_string = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(params) + f"&hash={signature}"
