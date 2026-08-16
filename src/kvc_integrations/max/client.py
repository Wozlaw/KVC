"""Direct httpx MAX Bot API client."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite

import httpx
from pydantic import SecretStr

from kvc_integrations.max.dto import MaxSentMessage, MaxTextFormat, MaxUpdatesBatch
from kvc_integrations.max.errors import (
    MaxApiAuthenticationError,
    MaxApiError,
    MaxApiRateLimitError,
    MaxApiRecipientError,
    MaxApiRequestError,
    MaxApiResponseError,
    MaxApiTemporaryError,
    MaxTransportError,
    MaxTransportTimeoutError,
)

JsonObject = dict[str, object]
JsonMapping = Mapping[str, object]

MAX_MESSAGE_TEXT_LIMIT = 4000
MAX_UPDATES_LIMIT_MIN = 1
MAX_UPDATES_LIMIT_MAX = 1000
MAX_UPDATES_TIMEOUT_MIN = 0
MAX_UPDATES_TIMEOUT_MAX = 90


class MaxBotApiClient:
    """Small direct-httpx MAX Bot API client with safe provider error mapping."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        bot_token: str | SecretStr,
        api_base_url: str,
    ) -> None:
        self._client = client
        self._bot_token = _secret_value(bot_token)
        self._api_base_url = _normalize_base_url(api_base_url)
        if self._bot_token == "":
            raise MaxApiAuthenticationError("MAX API authentication is not configured")

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"api_base_url={self._api_base_url!r}, bot_token=SecretStr('**********'))"
        )

    async def send_message(
        self,
        *,
        chat_id: str | None = None,
        user_id: str | None = None,
        text: str,
        notify: bool = True,
        format: MaxTextFormat | None = None,
        attachments: Sequence[JsonMapping] | None = None,
    ) -> MaxSentMessage:
        """Send a MAX message to exactly one chat or user recipient."""

        params = _recipient_params(chat_id=chat_id, user_id=user_id)
        body: JsonObject = {"text": text, "notify": notify}
        if format is not None:
            body["format"] = format
        if attachments is not None:
            body["attachments"] = [dict(attachment) for attachment in attachments]

        payload = await self._request_json(
            "POST",
            "/messages",
            operation="send_message",
            params=params,
            json_body=body,
        )
        return _parse_sent_message(payload)

    async def get_updates(
        self,
        *,
        marker: str | None,
        limit: int,
        timeout_seconds: int,
        update_types: tuple[str, ...] | None = None,
    ) -> MaxUpdatesBatch:
        """Fetch MAX updates through the official Long Polling endpoint."""

        params = _updates_params(
            marker=marker,
            limit=limit,
            timeout_seconds=timeout_seconds,
            update_types=update_types,
        )
        payload = await self._request_json(
            "GET",
            "/updates",
            operation="get_updates",
            params=params,
        )
        return _parse_updates_batch(payload)

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        params: Mapping[str, str] | None = None,
        json_body: JsonMapping | None = None,
    ) -> JsonObject:
        url = self._build_url(path)
        try:
            response = await self._client.request(
                method,
                url,
                params=params,
                headers={"Authorization": self._bot_token},
                json=json_body,
            )
        except httpx.TimeoutException as exc:
            raise MaxTransportTimeoutError(
                "MAX API request timed out",
                operation=operation,
            ) from exc
        except httpx.TransportError as exc:
            raise MaxTransportError("MAX API transport unavailable", operation=operation) from exc

        if not 200 <= response.status_code < 300:
            raise _map_http_error(response, operation=operation)

        try:
            payload: object = response.json()
        except ValueError as exc:
            raise MaxApiResponseError(
                "Unexpected MAX API response",
                status_code=response.status_code,
                operation=operation,
            ) from exc

        if not isinstance(payload, dict):
            raise MaxApiResponseError(
                "Unexpected MAX API response",
                status_code=response.status_code,
                operation=operation,
            )
        return dict(payload)

    def _build_url(self, path: str) -> str:
        return f"{self._api_base_url}/{path.lstrip('/')}"


def _secret_value(secret: str | SecretStr) -> str:
    if isinstance(secret, SecretStr):
        return secret.get_secret_value()
    return secret


def _normalize_base_url(api_base_url: str) -> str:
    url = httpx.URL(api_base_url)
    if url.scheme not in {"http", "https"} or url.host is None or url.query or url.fragment:
        raise MaxApiRequestError("Invalid MAX API base URL")
    return str(url).rstrip("/")


def _recipient_params(*, chat_id: str | None, user_id: str | None) -> dict[str, str]:
    if (chat_id is None) == (user_id is None):
        raise MaxApiRequestError("Exactly one MAX message recipient is required")
    if chat_id is not None:
        return {"chat_id": chat_id}
    if user_id is None:
        raise MaxApiRequestError("Exactly one MAX message recipient is required")
    return {"user_id": user_id}


def _updates_params(
    *,
    marker: str | None,
    limit: int,
    timeout_seconds: int,
    update_types: tuple[str, ...] | None,
) -> dict[str, str]:
    if not MAX_UPDATES_LIMIT_MIN <= limit <= MAX_UPDATES_LIMIT_MAX:
        raise MaxApiRequestError("MAX updates limit is out of range")
    if not MAX_UPDATES_TIMEOUT_MIN <= timeout_seconds <= MAX_UPDATES_TIMEOUT_MAX:
        raise MaxApiRequestError("MAX updates timeout is out of range")

    params = {"limit": str(limit), "timeout": str(timeout_seconds)}
    if marker is not None:
        if marker.strip() == "":
            raise MaxApiRequestError("MAX updates marker is invalid")
        params["marker"] = marker
    if update_types is not None:
        if not update_types or any(update_type.strip() == "" for update_type in update_types):
            raise MaxApiRequestError("MAX update type filter is invalid")
        params["types"] = ",".join(update_types)
    return params


def _parse_sent_message(payload: JsonMapping) -> MaxSentMessage:
    message = payload.get("message")
    if not isinstance(message, dict):
        raise MaxApiResponseError("Unexpected MAX API response", operation="send_message")

    body = message.get("body")
    if body is not None and not isinstance(body, dict):
        raise MaxApiResponseError("Unexpected MAX API response", operation="send_message")

    recipient = message.get("recipient")
    if recipient is not None and not isinstance(recipient, dict):
        raise MaxApiResponseError("Unexpected MAX API response", operation="send_message")

    return MaxSentMessage(
        message_id=_optional_scalar_to_str(body.get("mid") if isinstance(body, dict) else None),
        chat_id=_optional_scalar_to_str(
            recipient.get("chat_id") if isinstance(recipient, dict) else None
        ),
        timestamp=_optional_int(message.get("timestamp")),
    )


def _parse_updates_batch(payload: JsonMapping) -> MaxUpdatesBatch:
    raw_updates = payload.get("updates")
    if not isinstance(raw_updates, list):
        raise MaxApiResponseError("Unexpected MAX API response", operation="get_updates")

    updates: list[Mapping[str, object]] = []
    for raw_update in raw_updates:
        if not isinstance(raw_update, dict):
            raise MaxApiResponseError("Unexpected MAX API response", operation="get_updates")
        updates.append(dict(raw_update))

    return MaxUpdatesBatch(
        updates=tuple(updates),
        marker=_optional_marker(payload.get("marker")),
    )


def _optional_marker(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise MaxApiResponseError("Unexpected MAX API response", operation="get_updates")
    if isinstance(value, int | str) and str(value) != "":
        return str(value)
    raise MaxApiResponseError("Unexpected MAX API response", operation="get_updates")


def _optional_scalar_to_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise MaxApiResponseError("Unexpected MAX API response", operation="send_message")
    if isinstance(value, int | str) and str(value) != "":
        return str(value)
    raise MaxApiResponseError("Unexpected MAX API response", operation="send_message")


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise MaxApiResponseError("Unexpected MAX API response", operation="send_message")
    if isinstance(value, int):
        return value
    raise MaxApiResponseError("Unexpected MAX API response", operation="send_message")


def _map_http_error(response: httpx.Response, *, operation: str) -> MaxApiError:
    status_code = response.status_code
    if status_code in {401, 403}:
        return MaxApiAuthenticationError(
            "MAX API authentication failed",
            status_code=status_code,
            operation=operation,
        )
    if status_code == 400:
        return MaxApiRequestError(
            "MAX API request rejected",
            status_code=status_code,
            operation=operation,
        )
    if status_code == 404:
        return MaxApiRecipientError(
            "MAX API recipient or resource not found",
            status_code=status_code,
            operation=operation,
        )
    if status_code == 429:
        return MaxApiRateLimitError(
            "MAX API rate limit exceeded",
            status_code=status_code,
            retry_after_seconds=_parse_retry_after(response.headers.get("Retry-After")),
            operation=operation,
        )
    if status_code >= 500 or status_code == 408:
        return MaxApiTemporaryError(
            "MAX API temporarily unavailable",
            status_code=status_code,
            operation=operation,
        )
    return MaxApiRequestError(
        "Unexpected MAX API status",
        status_code=status_code,
        operation=operation,
    )


def _parse_retry_after(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if not isfinite(parsed) or parsed < 0:
        return None
    return int(parsed)


__all__ = [
    "MAX_MESSAGE_TEXT_LIMIT",
    "MAX_UPDATES_LIMIT_MAX",
    "MAX_UPDATES_LIMIT_MIN",
    "MAX_UPDATES_TIMEOUT_MAX",
    "MAX_UPDATES_TIMEOUT_MIN",
    "MaxBotApiClient",
]
