"""Provider-boundary DTOs for MAX integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MaxUpdateSource = Literal["webhook", "long_polling"]
MaxChatType = Literal["PRIVATE", "GROUP", "CHANNEL", "UNKNOWN"]


@dataclass(frozen=True)
class MaxAttachmentMetadata:
    """Small normalized attachment metadata used by later routing."""

    attachment_type: str
    attachment_id: str | None = None
    name: str | None = None
    size: int | None = None


@dataclass(frozen=True)
class MaxIncomingUpdate:
    """Normalized provider-boundary inbound MAX update."""

    source: MaxUpdateSource
    update_type: str
    timestamp: int | None
    raw_event_type: str
    chat_id: str | None
    chat_type: MaxChatType
    max_user_id: str | None
    message_id: str | None
    message_text: str | None
    message_timestamp: int | None
    callback_payload: str | None
    attachments: tuple[MaxAttachmentMetadata, ...] = ()


@dataclass(frozen=True)
class ValidatedMaxMiniAppUser:
    """Trusted minimal MAX Mini App user identity after signature validation."""

    max_user_id: str


@dataclass(frozen=True)
class ValidatedMaxMiniAppChat:
    """Trusted minimal MAX Mini App chat identity after signature validation."""

    chat_id: str
    chat_type: MaxChatType


@dataclass(frozen=True)
class ValidatedMaxMiniAppInitData:
    """Safe normalized MAX Mini App launch data."""

    auth_date: int
    user: ValidatedMaxMiniAppUser
    chat: ValidatedMaxMiniAppChat | None
    start_param: str | None = None

    @property
    def max_user_id(self) -> str:
        return self.user.max_user_id

    @property
    def chat_id(self) -> str | None:
        if self.chat is None:
            return None
        return self.chat.chat_id

    @property
    def chat_type(self) -> MaxChatType:
        if self.chat is None:
            return "UNKNOWN"
        return self.chat.chat_type


__all__ = [
    "MaxAttachmentMetadata",
    "MaxChatType",
    "MaxIncomingUpdate",
    "MaxUpdateSource",
    "ValidatedMaxMiniAppChat",
    "ValidatedMaxMiniAppInitData",
    "ValidatedMaxMiniAppUser",
]
