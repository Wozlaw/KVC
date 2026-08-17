"""MAX Mini App notification settings route tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from kvc_api.main import create_app
from kvc_api.max.mini_app import MAX_INIT_DATA_HEADER, MAX_MINI_APP_CONTEXT_HEADER
from kvc_api.max.runtime import MaxMiniAppRuntime
from kvc_application.dto import (
    IdentityResolution,
    NotificationSettingsResult,
    UpdateNotificationSettingsInput,
)
from kvc_application.errors import (
    IdentityConflict,
    InvalidNotificationSettings,
    PersistenceConflict,
    UserDisabled,
)
from kvc_config import AppSettings
from kvc_integrations.max.context_signing import MiniAppContextPurpose, MiniAppContextSigner
from kvc_integrations.max.errors import MaxApiTemporaryError

BOT_TOKEN = "synthetic-bot-token"
CONTEXT_SECRET = "synthetic-context-secret"
MAX_USER_ID = "max-user-777"
MAX_CHAT_ID = "max-chat-777"
USER_ID = UUID("00000000-0000-0000-0000-000000000771")
BINDING_ID = UUID("00000000-0000-0000-0000-000000000772")
INIT_MARKER = "SYNTHETIC_INIT_MARKER_DO_NOT_LEAK"
CONTEXT_MARKER = "SYNTHETIC_CONTEXT_MARKER_DO_NOT_LEAK"


class FakeIdentityResolver:
    def __init__(
        self,
        *,
        user_status: str = "ACTIVE",
        exc: Exception | None = None,
    ) -> None:
        self.user_status = user_status
        self.exc = exc
        self.calls: list[object] = []

    async def resolve_or_onboard_private_max_user(self, input: object) -> IdentityResolution:
        self.calls.append(input)
        if self.exc is not None:
            raise self.exc
        return IdentityResolution(
            user_id=USER_ID,
            max_chat_binding_id=BINDING_ID,
            user_status="DISABLED" if self.user_status == "DISABLED" else "ACTIVE",
            is_new_user=False,
            kaiten_connection_status="ACTIVE",
        )


class FakeNotificationSettingsService:
    def __init__(
        self,
        *,
        result: NotificationSettingsResult | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.result = result or NotificationSettingsResult(USER_ID, True, 1, "UTC")
        self.exc = exc
        self.get_calls: list[UUID] = []
        self.update_calls: list[UpdateNotificationSettingsInput] = []

    async def get_settings(self, user_id: UUID) -> NotificationSettingsResult:
        self.get_calls.append(user_id)
        if self.exc is not None:
            raise self.exc
        return self.result

    async def update_settings(
        self,
        input: UpdateNotificationSettingsInput,
    ) -> NotificationSettingsResult:
        self.update_calls.append(input)
        if self.exc is not None:
            raise self.exc
        self.result = NotificationSettingsResult(
            input.user_id,
            input.enabled,
            input.due_soon_days,
            input.timezone.strip(),
        )
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


def test_notifications_page_serves_mobile_form_bridge_assets_and_safe_headers() -> None:
    client = TestClient(create_app(_settings()))

    response = client.get("/max/app/notifications")

    assert response.status_code == 200
    assert '<meta name="viewport"' in response.text
    assert "https://st.max.ru/js/max-web-app.js" in response.text
    assert "/max/app/static/app.css" in response.text
    assert "/max/app/static/notifications.js" in response.text
    assert 'id="enabled"' in response.text
    assert 'id="due-soon-days"' in response.text
    assert 'id="timezone"' in response.text
    assert 'id="save-button"' in response.text
    assert 'aria-live="polite"' in response.text
    assert "dashboard" not in response.text.lower()
    assert str(USER_ID) not in response.text
    assert MAX_USER_ID not in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors" not in response.headers["Content-Security-Policy"]
    assert "X-Frame-Options" not in response.headers


def test_notifications_script_uses_headers_and_no_browser_storage_or_logs() -> None:
    script = Path("src/kvc_api/max/static/notifications.js").read_text(encoding="utf-8")

    assert "/max/app/api/notifications" in script
    assert "X-KVC-Max-Init-Data" in script
    assert "X-KVC-Mini-App-Context" in script
    assert 'credentials: "same-origin"' in script
    assert "initData" in script
    assert "start_param" in script
    assert "initDataUnsafe" not in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "IndexedDB" not in script
    assert "console." not in script
    assert "kaiten" not in script.lower()


def test_get_notifications_returns_only_modeled_fields() -> None:
    identity = FakeIdentityResolver()
    service = FakeNotificationSettingsService(
        result=NotificationSettingsResult(USER_ID, False, 3, "Europe/Warsaw")
    )
    client = _client(identity=identity, notification_service=service)
    context_ref = _context_ref()

    response = client.get("/max/app/api/notifications", headers=_headers(context_ref))

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "due_soon_days": 3,
        "timezone": "Europe/Warsaw",
    }
    assert service.get_calls == [USER_ID]
    assert set(response.json()) == {"enabled", "due_soon_days", "timezone"}


def test_post_notifications_updates_through_service_and_confirms_once() -> None:
    service = FakeNotificationSettingsService()
    sender = FakeSender()
    client = _client(notification_service=service, sender=sender)
    context_ref = _context_ref()

    response = client.post(
        "/max/app/api/notifications",
        headers=_headers(context_ref),
        json={"enabled": False, "due_soon_days": 30, "timezone": " Asia/Tokyo "},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "saved",
        "settings": {"enabled": False, "due_soon_days": 30, "timezone": "Asia/Tokyo"},
        "confirmation_status": "sent",
    }
    assert service.update_calls == [
        UpdateNotificationSettingsInput(USER_ID, False, 30, " Asia/Tokyo ")
    ]
    assert sender.calls == [
        {
            "chat_id": MAX_CHAT_ID,
            "text": "Настройки уведомлений сохранены. Уведомления выключены.",
            "notify": True,
        }
    ]


def test_confirmation_failure_does_not_rollback_or_retry() -> None:
    service = FakeNotificationSettingsService()
    sender = FakeSender(exc=MaxApiTemporaryError("synthetic"))
    client = _client(notification_service=service, sender=sender)
    context_ref = _context_ref()

    response = client.post(
        "/max/app/api/notifications",
        headers=_headers(context_ref),
        json={"enabled": True, "due_soon_days": 3, "timezone": "UTC"},
    )

    assert response.status_code == 200
    assert response.json()["confirmation_status"] == "failed"
    assert service.update_calls == [UpdateNotificationSettingsInput(USER_ID, True, 3, "UTC")]
    assert len(sender.calls) == 1


def test_invalid_settings_do_not_send_confirmation() -> None:
    service = FakeNotificationSettingsService(exc=InvalidNotificationSettings("synthetic"))
    sender = FakeSender()
    client = _client(notification_service=service, sender=sender)
    context_ref = _context_ref()

    response = client.post(
        "/max/app/api/notifications",
        headers=_headers(context_ref),
        json={"enabled": True, "due_soon_days": 31, "timezone": "UTC"},
    )

    assert response.status_code == 400
    assert response.json() == {"status": "invalid_settings"}
    assert sender.calls == []


def test_unknown_fields_are_rejected_before_service_call() -> None:
    service = FakeNotificationSettingsService()
    client = _client(notification_service=service)
    context_ref = _context_ref()

    response = client.post(
        "/max/app/api/notifications",
        headers=_headers(context_ref),
        json={"enabled": True, "due_soon_days": 3, "timezone": "UTC", "user_id": str(USER_ID)},
    )

    assert response.status_code == 400
    assert response.json() == {"status": "invalid_settings"}
    assert service.update_calls == []


def test_invalid_launch_or_context_does_not_call_services_or_leak_headers(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    identity = FakeIdentityResolver()
    service = FakeNotificationSettingsService()
    client = _client(identity=identity, notification_service=service)

    response = client.get(
        "/max/app/api/notifications",
        headers={
            MAX_INIT_DATA_HEADER: f"bad={INIT_MARKER}",
            MAX_MINI_APP_CONTEXT_HEADER: CONTEXT_MARKER,
        },
    )

    assert response.status_code == 403
    assert response.json() == {"status": "invalid_launch"}
    assert identity.calls == []
    assert service.get_calls == []
    assert INIT_MARKER not in response.text
    assert CONTEXT_MARKER not in response.text
    captured = capsys.readouterr()
    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert INIT_MARKER not in captured.out
    assert INIT_MARKER not in captured.err
    assert INIT_MARKER not in rendered_logs
    assert CONTEXT_MARKER not in captured.out
    assert CONTEXT_MARKER not in captured.err
    assert CONTEXT_MARKER not in rendered_logs


def test_expired_launch_maps_to_safe_status_without_echo() -> None:
    context_ref = _context_ref()
    client = _client()

    response = client.get(
        "/max/app/api/notifications",
        headers=_headers(context_ref, auth_date=int(time.time()) - 3601),
    )

    assert response.status_code == 409
    assert response.json() == {"status": "expired_launch"}
    assert context_ref not in response.text


def test_expired_context_maps_to_safe_status() -> None:
    context_ref = _context_ref(ttl_seconds=1, now=int(time.time()) - 2)
    client = _client()

    response = client.get("/max/app/api/notifications", headers=_headers(context_ref))

    assert response.status_code == 409
    assert response.json() == {"status": "expired_context"}


def test_wrong_context_purpose_user_chat_and_non_private_are_rejected() -> None:
    client = _client()
    wrong_purpose = _context_ref(purpose=MiniAppContextPurpose.CONNECT_KAITEN)
    wrong_user = _context_ref(max_user_id="other-user")
    wrong_chat = _context_ref(chat_id="other-chat")

    responses = [
        client.get("/max/app/api/notifications", headers=_headers(wrong_purpose)),
        client.get("/max/app/api/notifications", headers=_headers(wrong_user)),
        client.get("/max/app/api/notifications", headers=_headers(wrong_chat)),
        client.get(
            "/max/app/api/notifications",
            headers=_headers(_context_ref(), chat_type="chat"),
        ),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403]
    assert [response.json()["status"] for response in responses] == [
        "invalid_context",
        "invalid_context",
        "invalid_context",
        "private_chat_required",
    ]


def test_disabled_user_after_context_issue_is_blocked() -> None:
    service = FakeNotificationSettingsService()
    client = _client(
        identity=FakeIdentityResolver(user_status="DISABLED"),
        notification_service=service,
    )
    context_ref = _context_ref()

    response = client.get("/max/app/api/notifications", headers=_headers(context_ref))

    assert response.status_code == 403
    assert response.json() == {"status": "user_disabled"}
    assert service.get_calls == []


def test_service_user_disabled_and_persistence_errors_map_safely() -> None:
    for exc, expected_status, expected_body in [
        (UserDisabled("synthetic"), 403, {"status": "user_disabled"}),
        (PersistenceConflict("synthetic"), 503, {"status": "temporary_failure"}),
        (IdentityConflict("synthetic"), 409, {"status": "identity_conflict"}),
    ]:
        identity = (
            FakeIdentityResolver(exc=exc)
            if isinstance(exc, IdentityConflict)
            else FakeIdentityResolver()
        )
        service = (
            FakeNotificationSettingsService()
            if isinstance(exc, IdentityConflict)
            else FakeNotificationSettingsService(exc=exc)
        )
        client = _client(identity=identity, notification_service=service)
        context_ref = _context_ref()

        response = client.get("/max/app/api/notifications", headers=_headers(context_ref))

        assert response.status_code == expected_status
        assert response.json() == expected_body


def test_runtime_or_configuration_missing_is_safe() -> None:
    context_ref = _context_ref()
    no_runtime = TestClient(create_app(_settings()))
    no_secret = TestClient(
        create_app(AppSettings(_env_file=None, max_bot_token=SecretStr(BOT_TOKEN)))
    )

    first = no_runtime.get("/max/app/api/notifications", headers=_headers(context_ref))
    second = no_secret.get("/max/app/api/notifications", headers=_headers(context_ref))

    assert first.status_code == 503
    assert first.json() == {"status": "unavailable"}
    assert second.status_code == 503
    assert second.json() == {"status": "configuration_error"}


def _client(
    *,
    identity: FakeIdentityResolver | None = None,
    notification_service: FakeNotificationSettingsService | None = None,
    sender: FakeSender | None = None,
) -> TestClient:
    runtime = MaxMiniAppRuntime(
        identity_resolver_factory=lambda: identity or FakeIdentityResolver(),
        kaiten_connection_binder_factory=lambda: object(),  # type: ignore[arg-type]
        message_sender=sender or FakeSender(),
        context_signer=MiniAppContextSigner(CONTEXT_SECRET),
        notification_settings_service_factory=lambda: (
            notification_service or FakeNotificationSettingsService()
        ),
    )
    return TestClient(create_app(_settings(), max_mini_app_runtime=runtime))


def _settings() -> AppSettings:
    return AppSettings(
        max_bot_token=SecretStr(BOT_TOKEN),
        max_mini_app_context_secret=SecretStr(CONTEXT_SECRET),
    )


def _headers(
    context_ref: str,
    *,
    auth_date: int | None = None,
    chat_type: str = "dialog",
) -> dict[str, str]:
    return {
        MAX_INIT_DATA_HEADER: _signed_init_data(
            auth_date=auth_date,
            start_param=context_ref,
            chat_type=chat_type,
        ),
        MAX_MINI_APP_CONTEXT_HEADER: context_ref,
    }


def _context_ref(
    *,
    purpose: MiniAppContextPurpose = MiniAppContextPurpose.NOTIFICATION_SETTINGS,
    max_user_id: str = MAX_USER_ID,
    chat_id: str = MAX_CHAT_ID,
    ttl_seconds: int = 1800,
    now: int | None = None,
) -> str:
    signer = MiniAppContextSigner(CONTEXT_SECRET)
    binding = signer.make_identity_binding(max_user_id=max_user_id, chat_id=chat_id)
    return signer.issue(
        purpose=purpose,
        identity_binding=binding,
        ttl_seconds=ttl_seconds,
        now=int(time.time()) if now is None else now,
        nonce=f"nonce-{purpose.value}",
    )


def _signed_init_data(
    *,
    auth_date: int | None = None,
    start_param: str,
    chat_type: str = "dialog",
    bot_token: str = BOT_TOKEN,
) -> str:
    params: dict[str, str] = {
        "auth_date": str(auth_date or int(time.time())),
        "user": json.dumps({"id": MAX_USER_ID}, separators=(",", ":")),
        "chat": json.dumps({"id": MAX_CHAT_ID, "type": chat_type}, separators=(",", ":")),
        "start_param": start_param,
    }
    data_check_string = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(params) + f"&hash={signature}"
