"""MAX webhook route integration tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

from kvc_api.main import create_app
from kvc_api.max.dispatcher import WebhookRetryableDispatchError
from kvc_config import AppSettings
from kvc_integrations.max.dto import MaxIncomingUpdate

WEBHOOK_SECRET = "SYNTHETIC-WEBHOOK-SECRET"


def private_message_update() -> dict[str, object]:
    return {
        "update_type": "message_created",
        "timestamp": 1_700_000_000_000,
        "message": {
            "sender": {"user_id": 123},
            "recipient": {"chat_id": 456, "chat_type": "dialog"},
            "body": {"mid": "mid-1", "text": "/start"},
        },
    }


class FakeDispatcher:
    def __init__(self, *, exc: Exception | None = None) -> None:
        self.calls: list[MaxIncomingUpdate] = []
        self.exc = exc

    async def dispatch(self, update: MaxIncomingUpdate) -> object:
        self.calls.append(update)
        if self.exc is not None:
            raise self.exc
        return object()


def client_with_dispatcher(dispatcher: FakeDispatcher) -> TestClient:
    settings = AppSettings(max_webhook_secret=SecretStr(WEBHOOK_SECRET))
    return TestClient(create_app(settings, max_dispatcher=dispatcher))


def test_webhook_accepts_valid_secret_and_dispatches_private_message() -> None:
    dispatcher = FakeDispatcher()
    client = client_with_dispatcher(dispatcher)

    response = client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": WEBHOOK_SECRET},
        json=private_message_update(),
    )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    assert dispatcher.calls[0].chat_type == "PRIVATE"
    assert dispatcher.calls[0].message_text == "/start"


def test_webhook_rejects_bad_secret_before_dispatch_without_echo() -> None:
    dispatcher = FakeDispatcher()
    client = client_with_dispatcher(dispatcher)

    response = client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": "bad-secret"},
        json=private_message_update(),
    )

    assert response.status_code == 403
    assert dispatcher.calls == []
    assert "bad-secret" not in response.text
    assert WEBHOOK_SECRET not in response.text


def test_webhook_rejects_missing_secret_when_configured() -> None:
    dispatcher = FakeDispatcher()
    client = client_with_dispatcher(dispatcher)

    response = client.post("/max/webhook", json=private_message_update())

    assert response.status_code == 403
    assert dispatcher.calls == []


def test_webhook_malformed_json_returns_safe_400() -> None:
    dispatcher = FakeDispatcher()
    client = client_with_dispatcher(dispatcher)

    response = client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": WEBHOOK_SECRET},
        content="{not-json",
    )

    assert response.status_code == 400
    assert response.json() == {"status": "invalid_json"}
    assert dispatcher.calls == []


def test_webhook_malformed_update_returns_safe_400() -> None:
    dispatcher = FakeDispatcher()
    client = client_with_dispatcher(dispatcher)

    response = client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": WEBHOOK_SECRET},
        json={"timestamp": 1},
    )

    assert response.status_code == 400
    assert response.json() == {"status": "invalid_update"}
    assert dispatcher.calls == []


def test_webhook_unsupported_update_dispatches_and_returns_200() -> None:
    dispatcher = FakeDispatcher()
    client = client_with_dispatcher(dispatcher)

    response = client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": WEBHOOK_SECRET},
        json={"update_type": "message_removed", "timestamp": 1},
    )

    assert response.status_code == 200
    assert dispatcher.calls[0].update_type == "message_removed"


def test_webhook_retryable_dispatch_failure_returns_503() -> None:
    dispatcher = FakeDispatcher(exc=WebhookRetryableDispatchError("retry"))
    client = client_with_dispatcher(dispatcher)

    response = client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": WEBHOOK_SECRET},
        json=private_message_update(),
    )

    assert response.status_code == 503
    assert response.json() == {"status": "retryable_failure"}


def test_webhook_without_runtime_dependencies_returns_503_without_breaking_health() -> None:
    client = TestClient(create_app(AppSettings(max_webhook_secret=SecretStr(WEBHOOK_SECRET))))

    health = client.get("/health")
    webhook = client.post(
        "/max/webhook",
        headers={"X-Max-Bot-Api-Secret": WEBHOOK_SECRET},
        json=private_message_update(),
    )

    assert health.status_code == 200
    assert webhook.status_code == 503
