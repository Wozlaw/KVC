"""MAX Bot API direct HTTP client tests."""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from kvc_integrations.max import (
    MAX_MESSAGE_TEXT_LIMIT,
    MAX_UPDATES_LIMIT_MAX,
    MAX_UPDATES_TIMEOUT_MAX,
    MaxBotApiClient,
    MaxSentMessage,
    MaxUpdatesBatch,
)
from kvc_integrations.max.errors import (
    MaxApiAuthenticationError,
    MaxApiRateLimitError,
    MaxApiRecipientError,
    MaxApiRequestError,
    MaxApiResponseError,
    MaxApiTemporaryError,
    MaxTransportError,
    MaxTransportTimeoutError,
)

TOKEN_MARKER = "SYNTHETIC-MAX-TOKEN-MUST-NOT-LEAK"
BODY_MARKER = "SYNTHETIC-MAX-BODY-MUST-NOT-LEAK"


def _success_payload() -> dict[str, object]:
    return {
        "message": {
            "timestamp": 1_700_000_000_000,
            "recipient": {"chat_id": 456},
            "body": {"mid": "mid-1"},
        }
    }


@pytest.mark.asyncio
async def test_client_sends_request_scoped_authorization_and_normalizes_result() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["query"] = dict(request.url.params)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = body
        captured["token_in_url"] = TOKEN_MARKER in str(request.url)
        captured["token_in_body"] = TOKEN_MARKER in request.content.decode("utf-8")
        return httpx.Response(200, json=_success_payload())

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"X-Shared": "safe"},
    ) as http_client:
        client = MaxBotApiClient(
            http_client,
            bot_token=SecretStr(TOKEN_MARKER),
            api_base_url="https://platform-api2.max.ru/",
        )

        result = await client.send_message(chat_id="456", text="hello")

        assert result == MaxSentMessage(
            message_id="mid-1", chat_id="456", timestamp=1_700_000_000_000
        )
        assert captured == {
            "method": "POST",
            "path": "/messages",
            "query": {"chat_id": "456"},
            "auth": TOKEN_MARKER,
            "body": {"text": "hello", "notify": True},
            "token_in_url": False,
            "token_in_body": False,
        }
        assert "Authorization" not in http_client.headers
        assert TOKEN_MARKER not in repr(client)


@pytest.mark.asyncio
async def test_client_preserves_base_url_path_without_double_slashes() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json=_success_payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru/bot-api/",
        )

        await client.send_message(chat_id="456", text="hello")

    assert paths == ["/bot-api/messages"]


@pytest.mark.parametrize(
    ("status_code", "error_type", "retryable"),
    [
        (400, MaxApiRequestError, False),
        (401, MaxApiAuthenticationError, False),
        (403, MaxApiAuthenticationError, False),
        (404, MaxApiRecipientError, False),
        (429, MaxApiRateLimitError, True),
        (500, MaxApiTemporaryError, True),
        (503, MaxApiTemporaryError, True),
    ],
)
@pytest.mark.asyncio
async def test_client_maps_provider_status_safely(
    status_code: int,
    error_type: type[Exception],
    retryable: bool,
) -> None:
    response = httpx.Response(status_code, text=BODY_MARKER, headers={"Retry-After": "3"})
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response)
    ) as http_client:
        client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru",
        )

        with pytest.raises(error_type) as caught:
            await client.send_message(chat_id="456", text="hello")

    assert isinstance(
        caught.value,
        MaxApiRequestError
        | MaxApiAuthenticationError
        | MaxApiTemporaryError
        | MaxApiRateLimitError,
    )
    assert caught.value.retryable is retryable
    assert caught.value.status_code == status_code
    rendered = f"{caught.value!s} {caught.value!r}"
    assert TOKEN_MARKER not in rendered
    assert BODY_MARKER not in rendered
    assert "Authorization" not in rendered


@pytest.mark.asyncio
async def test_client_captures_numeric_retry_after_and_ignores_malformed_values() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        retry_after = "7" if calls == 1 else "not-a-number"
        return httpx.Response(429, headers={"Retry-After": retry_after})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru",
        )

        with pytest.raises(MaxApiRateLimitError) as first:
            await client.send_message(chat_id="456", text="hello")
        with pytest.raises(MaxApiRateLimitError) as second:
            await client.send_message(chat_id="456", text="hello")

    assert first.value.retry_after_seconds == 7
    assert second.value.retry_after_seconds is None


@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (httpx.TimeoutException("synthetic timeout"), MaxTransportTimeoutError),
        (httpx.ConnectError("synthetic connect failure"), MaxTransportError),
    ],
)
@pytest.mark.asyncio
async def test_client_maps_transport_failures(
    exception: httpx.TransportError,
    error_type: type[Exception],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exception

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru",
        )

        with pytest.raises(error_type) as caught:
            await client.send_message(chat_id="456", text="hello")

    assert caught.value.retryable is True
    rendered = f"{caught.value!s} {caught.value!r}"
    assert TOKEN_MARKER not in rendered
    assert "synthetic" not in rendered


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text=f"not-json-{BODY_MARKER}"),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"message": []}),
        httpx.Response(200, json={"message": {"body": []}}),
        httpx.Response(200, json={"message": {"recipient": []}}),
        httpx.Response(200, json={"message": {"timestamp": "bad"}}),
        httpx.Response(200, json={"message": {"body": {"mid": ""}}}),
    ],
)
@pytest.mark.asyncio
async def test_client_maps_malformed_success_payload_safely(response: httpx.Response) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response)
    ) as http_client:
        client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru",
        )

        with pytest.raises(MaxApiResponseError) as caught:
            await client.send_message(chat_id="456", text="hello")

    rendered = f"{caught.value!s} {caught.value!r}"
    assert TOKEN_MARKER not in rendered
    assert BODY_MARKER not in rendered


@pytest.mark.parametrize(
    "kwargs",
    [
        {"chat_id": "456", "user_id": "123"},
        {},
    ],
)
@pytest.mark.asyncio
async def test_client_rejects_nonexclusive_recipient_without_http(
    kwargs: dict[str, str],
) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, json=_success_payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru",
        )

        with pytest.raises(MaxApiRequestError):
            await client.send_message(text="hello", **kwargs)

    assert request_count == 0


@pytest.mark.parametrize(
    "status_code",
    [429, 500],
)
@pytest.mark.asyncio
async def test_client_does_not_retry_retryable_provider_status(status_code: int) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(status_code)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru",
        )

        with pytest.raises(MaxApiRateLimitError if status_code == 429 else MaxApiTemporaryError):
            await client.send_message(chat_id="456", text="hello")

    assert request_count == 1


def test_client_rejects_blank_token_and_invalid_base_url_safely() -> None:
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    with pytest.raises(MaxApiAuthenticationError) as token_error:
        MaxBotApiClient(http_client, bot_token="", api_base_url="https://platform-api2.max.ru")
    with pytest.raises(MaxApiRequestError) as url_error:
        MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url=f"https://platform-api2.max.ru?token={TOKEN_MARKER}",
        )

    rendered = (
        f"{token_error.value!s} {token_error.value!r} {url_error.value!s} {url_error.value!r}"
    )
    assert TOKEN_MARKER not in rendered


def test_max_message_text_limit_matches_official_documented_bound() -> None:
    assert MAX_MESSAGE_TEXT_LIMIT == 4000


@pytest.mark.asyncio
async def test_client_get_updates_request_shape_and_marker_progression() -> None:
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "method": request.method,
                "path": request.url.path,
                "query": dict(request.url.params),
                "auth": request.headers.get("Authorization"),
                "token_in_url": TOKEN_MARKER in str(request.url),
                "has_body": request.content != b"",
            }
        )
        marker = 100 if len(captured) == 1 else 200
        return httpx.Response(
            200,
            json={
                "updates": [{"update_type": "message_created", "timestamp": 1}],
                "marker": marker,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru",
        )

        first = await client.get_updates(
            marker=None,
            limit=100,
            timeout_seconds=60,
            update_types=("message_created", "message_callback"),
        )
        second = await client.get_updates(
            marker=first.marker,
            limit=100,
            timeout_seconds=60,
            update_types=("message_created", "message_callback"),
        )

    assert first == MaxUpdatesBatch(
        updates=({"update_type": "message_created", "timestamp": 1},),
        marker="100",
    )
    assert second.marker == "200"
    assert captured == [
        {
            "method": "GET",
            "path": "/updates",
            "query": {
                "limit": "100",
                "timeout": "60",
                "types": "message_created,message_callback",
            },
            "auth": TOKEN_MARKER,
            "token_in_url": False,
            "has_body": False,
        },
        {
            "method": "GET",
            "path": "/updates",
            "query": {
                "limit": "100",
                "timeout": "60",
                "marker": "100",
                "types": "message_created,message_callback",
            },
            "auth": TOKEN_MARKER,
            "token_in_url": False,
            "has_body": False,
        },
    ]


@pytest.mark.parametrize(
    ("marker", "limit", "timeout_seconds", "update_types"),
    [
        (None, 0, 60, None),
        (None, MAX_UPDATES_LIMIT_MAX + 1, 60, None),
        (None, 100, -1, None),
        (None, 100, MAX_UPDATES_TIMEOUT_MAX + 1, None),
        ("", 100, 60, None),
        (None, 100, 60, ()),
        (None, 100, 60, ("",)),
    ],
)
@pytest.mark.asyncio
async def test_client_get_updates_rejects_invalid_local_inputs_without_http(
    marker: str | None,
    limit: int,
    timeout_seconds: int,
    update_types: tuple[str, ...] | None,
) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, json={"updates": [], "marker": None})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru",
        )

        with pytest.raises(MaxApiRequestError):
            await client.get_updates(
                marker=marker,
                limit=limit,
                timeout_seconds=timeout_seconds,
                update_types=update_types,
            )

    assert request_count == 0


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text=f"not-json-{BODY_MARKER}"),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"updates": {}}),
        httpx.Response(200, json={"updates": [1]}),
        httpx.Response(200, json={"updates": [], "marker": True}),
        httpx.Response(200, json={"updates": [], "marker": ""}),
    ],
)
@pytest.mark.asyncio
async def test_client_get_updates_maps_malformed_success_payload_safely(
    response: httpx.Response,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response)
    ) as http_client:
        client = MaxBotApiClient(
            http_client,
            bot_token=TOKEN_MARKER,
            api_base_url="https://platform-api2.max.ru",
        )

        with pytest.raises(MaxApiResponseError) as caught:
            await client.get_updates(marker=None, limit=100, timeout_seconds=60)

    rendered = f"{caught.value!s} {caught.value!r}"
    assert TOKEN_MARKER not in rendered
    assert BODY_MARKER not in rendered
