"""Outbound MAX message sender."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from kvc_integrations.max.client import MAX_MESSAGE_TEXT_LIMIT, MaxBotApiClient
from kvc_integrations.max.dto import MaxSentMessage, MaxTextFormat
from kvc_integrations.max.errors import MaxApiRequestError

MAX_STARTAPP_CONTEXT_LIMIT = 512
_STARTAPP_CONTEXT_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class MaxMessageSender:
    """Provider adapter for outbound MAX messaging operations."""

    def __init__(
        self,
        api_client: MaxBotApiClient,
        *,
        mini_app_public_url: str | None = None,
    ) -> None:
        self._api_client = api_client
        self._mini_app_public_url = (
            None
            if mini_app_public_url is None
            else _validate_mini_app_public_url(mini_app_public_url)
        )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"api_client={self._api_client!r}, mini_app_public_url=<redacted>)"
        )

    async def send_text_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        format: MaxTextFormat | None = None,
        notify: bool = True,
    ) -> MaxSentMessage:
        _validate_non_blank("chat_id", chat_id)
        _validate_text(text)
        return await self._api_client.send_message(
            chat_id=chat_id,
            text=text,
            notify=notify,
            format=format,
        )

    async def send_text_to_user(
        self,
        *,
        user_id: str,
        text: str,
        format: MaxTextFormat | None = None,
        notify: bool = True,
    ) -> MaxSentMessage:
        _validate_non_blank("user_id", user_id)
        _validate_text(text)
        return await self._api_client.send_message(
            user_id=user_id,
            text=text,
            notify=notify,
            format=format,
        )

    async def send_open_app_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        context_ref: str,
        label: str,
        app_path: str | None = None,
        format: MaxTextFormat | None = None,
        notify: bool = True,
    ) -> MaxSentMessage:
        _validate_non_blank("chat_id", chat_id)
        _validate_text(text)
        _validate_label(label)
        _validate_context_ref(context_ref)
        if self._mini_app_public_url is None:
            raise MaxApiRequestError("MAX Mini App public URL is required")
        launch_url = _with_startapp_context(
            self._mini_app_public_url,
            context_ref,
            app_path=app_path,
        )
        attachment = {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "open_app",
                            "text": label,
                            "web_app": launch_url,
                        }
                    ]
                ]
            },
        }
        return await self._api_client.send_message(
            chat_id=chat_id,
            text=text,
            notify=notify,
            format=format,
            attachments=[attachment],
        )


def _validate_non_blank(field_name: str, value: str) -> None:
    if value.strip() == "":
        raise MaxApiRequestError(f"MAX {field_name} is required")


def _validate_text(text: str) -> None:
    if text == "":
        raise MaxApiRequestError("MAX message text is required")
    if len(text) > MAX_MESSAGE_TEXT_LIMIT:
        raise MaxApiRequestError("MAX message text is too long")


def _validate_label(label: str) -> None:
    if label.strip() == "":
        raise MaxApiRequestError("MAX open_app button label is required")


def _validate_context_ref(context_ref: str) -> None:
    if context_ref == "":
        raise MaxApiRequestError("MAX Mini App context reference is required")
    if len(context_ref) > MAX_STARTAPP_CONTEXT_LIMIT or not _STARTAPP_CONTEXT_RE.fullmatch(
        context_ref
    ):
        raise MaxApiRequestError("MAX Mini App context reference is invalid")


def _validate_mini_app_public_url(mini_app_public_url: str) -> str:
    url = httpx.URL(mini_app_public_url)
    if url.scheme != "https" or url.host is None or url.fragment:
        raise MaxApiRequestError("Invalid MAX Mini App public URL")
    return str(url)


def _with_startapp_context(base_url: str, context_ref: str, *, app_path: str | None = None) -> str:
    parsed = urlsplit(base_url)
    path = parsed.path
    if app_path is not None:
        if not app_path.startswith("/") or app_path.startswith("//"):
            raise MaxApiRequestError("MAX Mini App path is invalid")
        path = app_path
    query = [(key, value) for key, value in parse_qsl(parsed.query) if key != "startapp"]
    query.append(("startapp", context_ref))
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            path,
            urlencode(query, safe="-_"),
            "",
        )
    )


__all__ = ["MAX_STARTAPP_CONTEXT_LIMIT", "MaxMessageSender"]
