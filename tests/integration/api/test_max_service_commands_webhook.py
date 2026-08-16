"""Webhook integration tests for final MAX service command UX."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr

from kvc_api.main import create_app
from kvc_api.max.dispatcher import UpdateDispatcher
from kvc_api.max.service_commands import ServiceCommandHandler
from kvc_application.dto import (
    IdentityResolution,
    KaitenConnectionResult,
    ResolveMaxIdentityInput,
)
from kvc_config import AppSettings
from kvc_integrations.max.context_signing import MiniAppContextPurpose, MiniAppContextSigner
from kvc_integrations.max.dto import MaxSentMessage

WEBHOOK_SECRET = "SYNTHETIC-WEBHOOK-SECRET"
CONTEXT_SECRET = "synthetic-context-secret"
USER_ID = UUID("00000000-0000-0000-0000-000000000501")


class FakeIdentity:
    def __init__(self, *, connection_status: str | None = None) -> None:
        self.connection_status = connection_status
        self.calls: list[ResolveMaxIdentityInput] = []

    async def resolve_or_onboard_private_max_user(
        self,
        input: ResolveMaxIdentityInput,
    ) -> IdentityResolution:
        self.calls.append(input)
        return IdentityResolution(
            user_id=USER_ID,
            max_chat_binding_id=uuid4(),
            user_status="ACTIVE",
            is_new_user=False,
            kaiten_connection_status=self.connection_status,  # type: ignore[arg-type]
        )


class FakeDisabler:
    def __init__(self) -> None:
        self.calls: list[UUID] = []

    async def disable_connection(self, user_id: UUID) -> KaitenConnectionResult:
        self.calls.append(user_id)
        return KaitenConnectionResult(
            connection_id=uuid4(),
            user_id=user_id,
            status="DISABLED",
            api_base_url="https://synthetic.kaiten.example/api/latest",
            kaiten_user_id=None,
            workspace_id=None,
            last_verified_at=None,
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


def private_message_update(text: str) -> dict[str, object]:
    return {
        "update_type": "message_created",
        "timestamp": 1_700_000_000_000,
        "message": {
            "sender": {"user_id": "max-user-1"},
            "recipient": {"chat_id": "max-chat-1", "chat_type": "dialog"},
            "body": {"mid": "mid-1", "text": text},
        },
    }


def client(
    *,
    identity: FakeIdentity,
    sender: FakeSender,
    disabler: FakeDisabler | None = None,
) -> TestClient:
    dispatcher = UpdateDispatcher(
        identity_service=identity,
        message_sender=sender,
        service_command_handler=ServiceCommandHandler(
            context_signer=MiniAppContextSigner(CONTEXT_SECRET),
            kaiten_connection_service_factory=None if disabler is None else lambda: disabler,
            mini_app_launch_enabled=True,
            now=lambda: 1_700_000_000,
        ),
        allowed_update_types=("message_created", "message_callback", "bot_started"),
    )
    return TestClient(
        create_app(
            AppSettings(max_webhook_secret=SecretStr(WEBHOOK_SECRET)),
            max_dispatcher=dispatcher,
        )
    )


def post_command(test_client: TestClient, command: str) -> object:
    return test_client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": WEBHOOK_SECRET},
        json=private_message_update(command),
    )


def test_webhook_connect_missing_connection_sends_open_app() -> None:
    identity = FakeIdentity()
    sender = FakeSender()

    response = post_command(client(identity=identity, sender=sender), "/connect")

    assert response.status_code == 200
    assert sender.text_calls == []
    assert len(sender.open_app_calls) == 1
    assert sender.open_app_calls[0][0] == "max-chat-1"
    assert sender.open_app_calls[0][3] == "Подключить Kaiten"
    assert "." not in sender.open_app_calls[0][2]


def test_webhook_connect_active_replies_without_open_app() -> None:
    identity = FakeIdentity(connection_status="ACTIVE")
    sender = FakeSender()

    response = post_command(client(identity=identity, sender=sender), "/connect")

    assert response.status_code == 200
    assert sender.open_app_calls == []
    assert "уже подключён" in sender.text_calls[0][1]


def test_webhook_reconnect_active_sends_open_app() -> None:
    identity = FakeIdentity(connection_status="ACTIVE")
    sender = FakeSender()

    response = post_command(client(identity=identity, sender=sender), "/reconnect")

    assert response.status_code == 200
    assert len(sender.open_app_calls) == 1
    assert sender.open_app_calls[0][3] == "Переподключить Kaiten"


def test_webhook_notifications_sends_notification_settings_open_app() -> None:
    identity = FakeIdentity(connection_status="ACTIVE")
    sender = FakeSender()

    response = post_command(client(identity=identity, sender=sender), "/notifications")

    assert response.status_code == 200
    assert sender.text_calls == []
    assert len(sender.open_app_calls) == 1
    chat_id, text, context_ref, label, app_path = sender.open_app_calls[0]
    binding = MiniAppContextSigner(CONTEXT_SECRET).make_identity_binding(
        max_user_id="max-user-1",
        chat_id="max-chat-1",
    )
    MiniAppContextSigner(CONTEXT_SECRET).verify(
        context_ref,
        expected_purpose=MiniAppContextPurpose.NOTIFICATION_SETTINGS,
        expected_identity_binding=binding,
        now=1_700_000_000,
    )
    assert chat_id == "max-chat-1"
    assert text == "Откройте Mini App, чтобы настроить уведомления."
    assert label == "Настроить уведомления"
    assert app_path == "/max/app/notifications"


def test_webhook_connection_and_status_use_safe_status_text() -> None:
    identity = FakeIdentity(connection_status="ACTIVE")
    sender = FakeSender()
    test_client = client(identity=identity, sender=sender)

    first = post_command(test_client, "/connection")
    second = post_command(test_client, "/status")

    assert first.status_code == 200
    assert second.status_code == 200
    assert sender.text_calls == [
        ("max-chat-1", "Kaiten подключён. Для замены используйте /reconnect."),
        ("max-chat-1", "Kaiten подключён. Для замены используйте /reconnect."),
    ]


def test_webhook_disable_calls_service_once_and_replies() -> None:
    identity = FakeIdentity(connection_status="ACTIVE")
    sender = FakeSender()
    disabler = FakeDisabler()

    response = post_command(client(identity=identity, sender=sender, disabler=disabler), "/disable")

    assert response.status_code == 200
    assert disabler.calls == [USER_ID]
    assert sender.text_calls == [("max-chat-1", "Подключение Kaiten отключено.")]
