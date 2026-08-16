"""MAX outbound message sender tests."""

from __future__ import annotations

import json
from collections.abc import Mapping

import httpx
import pytest

from kvc_integrations.max import (
    MAX_MESSAGE_TEXT_LIMIT,
    MaxBotApiClient,
    MaxMessageSender,
    MiniAppContextPurpose,
    MiniAppContextSigner,
)
from kvc_integrations.max.errors import MaxApiRateLimitError, MaxApiRequestError

TOKEN_MARKER = "SYNTHETIC-MAX-TOKEN-MUST-NOT-LEAK"
CONTEXT_MARKER = "ctx-ABC_123"
CONTEXT_SECRET = "synthetic-context-secret"


def _success_payload() -> dict[str, object]:
    return {
        "message": {
            "timestamp": 1_700_000_000_000,
            "recipient": {"chat_id": 456},
            "body": {"mid": "mid-1"},
        }
    }


async def _sender_with_capture(
    captured: list[tuple[httpx.Request, Mapping[str, object]]],
) -> tuple[httpx.AsyncClient, MaxMessageSender]:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured.append((request, body))
        return httpx.Response(200, json=_success_payload())

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    api_client = MaxBotApiClient(
        http_client,
        bot_token=TOKEN_MARKER,
        api_base_url="https://platform-api2.max.ru",
    )
    return http_client, MaxMessageSender(
        api_client,
        mini_app_public_url="https://max.ru/kvc_bot?lang=ru",
    )


@pytest.mark.asyncio
async def test_send_text_to_chat_uses_chat_recipient_and_minimal_body() -> None:
    captured: list[tuple[httpx.Request, Mapping[str, object]]] = []
    http_client, sender = await _sender_with_capture(captured)
    async with http_client:
        await sender.send_text_to_chat(chat_id="456", text="hello")

    request, body = captured[0]
    assert request.url.path == "/messages"
    assert dict(request.url.params) == {"chat_id": "456"}
    assert "user_id" not in request.url.params
    assert body == {"text": "hello", "notify": True}


@pytest.mark.asyncio
async def test_send_text_to_chat_can_disable_notify_and_set_format() -> None:
    captured: list[tuple[httpx.Request, Mapping[str, object]]] = []
    http_client, sender = await _sender_with_capture(captured)
    async with http_client:
        await sender.send_text_to_chat(
            chat_id="456",
            text="**hello**",
            notify=False,
            format="markdown",
        )

    request, body = captured[0]
    assert dict(request.url.params) == {"chat_id": "456"}
    assert body == {"text": "**hello**", "notify": False, "format": "markdown"}


@pytest.mark.asyncio
async def test_send_text_to_user_uses_user_recipient_only() -> None:
    captured: list[tuple[httpx.Request, Mapping[str, object]]] = []
    http_client, sender = await _sender_with_capture(captured)
    async with http_client:
        await sender.send_text_to_user(user_id="123", text="hello")

    request, body = captured[0]
    assert request.url.path == "/messages"
    assert dict(request.url.params) == {"user_id": "123"}
    assert "chat_id" not in request.url.params
    assert body == {"text": "hello", "notify": True}


@pytest.mark.asyncio
async def test_send_open_app_to_chat_builds_inline_open_app_button() -> None:
    captured: list[tuple[httpx.Request, Mapping[str, object]]] = []
    http_client, sender = await _sender_with_capture(captured)
    async with http_client:
        await sender.send_open_app_to_chat(
            chat_id="456",
            text="Connect Kaiten",
            context_ref=CONTEXT_MARKER,
            label="Open",
        )

    request, body = captured[0]
    assert request.url.path == "/messages"
    assert dict(request.url.params) == {"chat_id": "456"}
    assert body["text"] == "Connect Kaiten"
    assert body["notify"] is True
    attachments = body["attachments"]
    assert isinstance(attachments, list)
    assert attachments == [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "open_app",
                            "text": "Open",
                            "web_app": f"https://max.ru/kvc_bot?lang=ru&startapp={CONTEXT_MARKER}",
                        }
                    ]
                ]
            },
        }
    ]
    encoded_body = json.dumps(body)
    assert TOKEN_MARKER not in str(request.url)
    assert TOKEN_MARKER not in encoded_body
    assert "binding" not in encoded_body
    assert "purpose" not in encoded_body


@pytest.mark.asyncio
async def test_send_open_app_to_chat_accepts_current_signed_context_token() -> None:
    signer = MiniAppContextSigner(CONTEXT_SECRET)
    context_ref = signer.issue(
        purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        identity_binding=signer.make_identity_binding(max_user_id="123", chat_id="456"),
        ttl_seconds=900,
        now=1_700_000_000,
        nonce="sender-regression",
    )
    captured: list[tuple[httpx.Request, Mapping[str, object]]] = []
    http_client, sender = await _sender_with_capture(captured)
    async with http_client:
        await sender.send_open_app_to_chat(
            chat_id="456",
            text="Connect Kaiten",
            context_ref=context_ref,
            label="Open",
        )

    _, body = captured[0]
    attachment = body["attachments"][0]  # type: ignore[index]
    web_app = attachment["payload"]["buttons"][0][0]["web_app"]  # type: ignore[index]
    assert web_app == f"https://max.ru/kvc_bot?lang=ru&startapp={context_ref}"
    assert "%2E" not in web_app
    assert "." not in context_ref
    assert len(context_ref) <= 512


@pytest.mark.asyncio
async def test_send_open_app_to_chat_can_target_notification_page_path() -> None:
    captured: list[tuple[httpx.Request, Mapping[str, object]]] = []
    http_client, sender = await _sender_with_capture(captured)
    async with http_client:
        await sender.send_open_app_to_chat(
            chat_id="456",
            text="Notifications",
            context_ref=CONTEXT_MARKER,
            label="Open",
            app_path="/max/app/notifications",
        )

    _, body = captured[0]
    attachment = body["attachments"][0]  # type: ignore[index]
    web_app = attachment["payload"]["buttons"][0][0]["web_app"]  # type: ignore[index]
    assert web_app == f"https://max.ru/max/app/notifications?lang=ru&startapp={CONTEXT_MARKER}"


@pytest.mark.asyncio
async def test_sender_validation_accepts_text_bounds_without_mutating_text() -> None:
    captured: list[tuple[httpx.Request, Mapping[str, object]]] = []
    http_client, sender = await _sender_with_capture(captured)
    max_text = "a" * MAX_MESSAGE_TEXT_LIMIT
    async with http_client:
        await sender.send_text_to_chat(chat_id="456", text="a")
        await sender.send_text_to_chat(chat_id="456", text=max_text)

    assert captured[0][1]["text"] == "a"
    assert captured[1][1]["text"] == max_text


@pytest.mark.parametrize(
    ("method_name", "kwargs"),
    [
        ("send_text_to_chat", {"chat_id": "", "text": "hello"}),
        ("send_text_to_user", {"user_id": " ", "text": "hello"}),
        ("send_text_to_chat", {"chat_id": "456", "text": ""}),
        ("send_text_to_chat", {"chat_id": "456", "text": "a" * (MAX_MESSAGE_TEXT_LIMIT + 1)}),
        (
            "send_open_app_to_chat",
            {"chat_id": "456", "text": "hello", "context_ref": CONTEXT_MARKER, "label": ""},
        ),
        (
            "send_open_app_to_chat",
            {"chat_id": "456", "text": "hello", "context_ref": "", "label": "Open"},
        ),
        (
            "send_open_app_to_chat",
            {"chat_id": "456", "text": "hello", "context_ref": "ctx.with.dot", "label": "Open"},
        ),
    ],
)
@pytest.mark.asyncio
async def test_sender_rejects_invalid_input_before_http(
    method_name: str,
    kwargs: dict[str, str],
) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, json=_success_payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        api_client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru",
        )
        sender = MaxMessageSender(api_client, mini_app_public_url="https://max.ru/kvc_bot")
        method = getattr(sender, method_name)

        with pytest.raises(MaxApiRequestError) as caught:
            await method(**kwargs)

    assert request_count == 0
    rendered = f"{caught.value!s} {caught.value!r}"
    assert TOKEN_MARKER not in rendered
    context_ref = kwargs.get("context_ref")
    if context_ref:
        assert context_ref not in rendered


def test_sender_rejects_non_https_mini_app_public_url() -> None:
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    api_client = MaxBotApiClient(
        http_client,
        bot_token=TOKEN_MARKER,
        api_base_url="https://platform-api2.max.ru",
    )

    with pytest.raises(MaxApiRequestError):
        MaxMessageSender(api_client, mini_app_public_url="http://max.ru/kvc_bot")


@pytest.mark.asyncio
async def test_sender_does_not_retry_provider_rate_limit() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(429)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        api_client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru",
        )
        sender = MaxMessageSender(api_client, mini_app_public_url="https://max.ru/kvc_bot")

        with pytest.raises(MaxApiRateLimitError):
            await sender.send_text_to_chat(chat_id="456", text="hello")

    assert request_count == 1
