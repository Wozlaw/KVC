"""Application-layer data transfer contracts."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

MaxChatType = Literal["PRIVATE"]
UserStatus = Literal["ACTIVE", "DISABLED"]
KaitenConnectionStatus = Literal["ACTIVE", "DISABLED", "NEEDS_REAUTH"]
ContextInteractionStatus = Literal["completed", "cancelled"]

CONTEXT_INTERACTION_MAX_OPTIONS = 20
CONTEXT_INTERACTION_MAX_OPTION_ID_LENGTH = 128
CONTEXT_INTERACTION_MAX_LABEL_LENGTH = 160
CONTEXT_INTERACTION_MAX_DESCRIPTION_LENGTH = 300
CONTEXT_INTERACTION_MAX_TITLE_LENGTH = 120
CONTEXT_INTERACTION_MAX_PROMPT_LENGTH = 500
CONTEXT_INTERACTION_MAX_WORKFLOW_REF_LENGTH = 128
CONTEXT_INTERACTION_MAX_RESULT_MESSAGE_LENGTH = 500
CONTEXT_INTERACTION_WORKFLOW_REF_PATTERN = r"^[A-Za-z0-9_-]+$"
_CONTEXT_INTERACTION_WORKFLOW_REF_RE = re.compile(CONTEXT_INTERACTION_WORKFLOW_REF_PATTERN)


@dataclass(frozen=True)
class ResolveMaxIdentityInput:
    """Provider-neutral MAX private identity input."""

    max_user_id: str
    max_chat_id: str
    chat_type: MaxChatType


@dataclass(frozen=True)
class IdentityResolution:
    """Resolved KVC user identity for an incoming MAX private chat."""

    user_id: UUID
    max_chat_binding_id: UUID
    user_status: UserStatus
    is_new_user: bool
    kaiten_connection_status: KaitenConnectionStatus | None


@dataclass(frozen=True)
class BindKaitenConnectionInput:
    """Input for a future verified Kaiten credential bind or replacement."""

    user_id: UUID
    api_base_url: str
    plaintext_token: str = field(repr=False)


@dataclass(frozen=True)
class KaitenConnectionResult:
    """Non-secret Kaiten connection result."""

    connection_id: UUID
    user_id: UUID
    status: KaitenConnectionStatus
    api_base_url: str
    kaiten_user_id: str | None
    workspace_id: str | None
    last_verified_at: datetime | None


@dataclass(frozen=True)
class KaitenCredentialSnapshot:
    """Internal stored-credential snapshot for stale auth failure protection."""

    connection_id: UUID
    encrypted_api_token: bytes = field(repr=False)
    token_encryption_version: int


@dataclass(frozen=True)
class ActiveKaitenConnectionSecret:
    """Internal decrypted credential for a single imminent Kaiten workflow."""

    connection_id: UUID
    user_id: UUID
    api_base_url: str
    plaintext_token: str = field(repr=False)
    snapshot: KaitenCredentialSnapshot = field(repr=False)


@dataclass(frozen=True)
class MarkKaitenNeedsReauthInput:
    """Input for marking the current credential as needing reauthorization."""

    user_id: UUID
    snapshot: KaitenCredentialSnapshot = field(repr=False)
    reason: str = field(repr=False)


@dataclass(frozen=True)
class KaitenCredentialVerification:
    """Normalized result of checking a Kaiten credential."""

    kaiten_user_id: str | None
    workspace_id: str | None


@dataclass(frozen=True)
class EncryptedToken:
    """Encrypted token payload returned by a TokenCipher adapter."""

    ciphertext: bytes = field(repr=False)
    version: int


@dataclass(frozen=True)
class NotificationSettingsResult:
    """Provider-neutral notification settings snapshot."""

    user_id: UUID
    enabled: bool
    due_soon_days: int
    timezone: str


@dataclass(frozen=True)
class UpdateNotificationSettingsInput:
    """Input for updating per-user notification settings."""

    user_id: UUID
    enabled: bool
    due_soon_days: int
    timezone: str


@dataclass(frozen=True)
class ContextInteractionOption:
    """Bounded provider-neutral single-choice interaction option."""

    option_id: str
    label: str
    description: str | None = None

    def __post_init__(self) -> None:
        _require_bounded_text(
            self.option_id,
            "option_id",
            max_length=CONTEXT_INTERACTION_MAX_OPTION_ID_LENGTH,
        )
        _require_bounded_text(
            self.label,
            "label",
            max_length=CONTEXT_INTERACTION_MAX_LABEL_LENGTH,
        )
        _require_optional_bounded_text(
            self.description,
            "description",
            max_length=CONTEXT_INTERACTION_MAX_DESCRIPTION_LENGTH,
        )


@dataclass(frozen=True)
class ContextInteractionView:
    """Provider-neutral bounded single-choice interaction view."""

    workflow_ref: str
    title: str
    prompt: str
    options: Iterable[ContextInteractionOption]
    allow_cancel: bool = True

    def __post_init__(self) -> None:
        validate_context_interaction_workflow_ref(self.workflow_ref)
        _require_bounded_text(
            self.title,
            "title",
            max_length=CONTEXT_INTERACTION_MAX_TITLE_LENGTH,
        )
        _require_bounded_text(
            self.prompt,
            "prompt",
            max_length=CONTEXT_INTERACTION_MAX_PROMPT_LENGTH,
        )
        options = tuple(self.options)
        if not 1 <= len(options) <= CONTEXT_INTERACTION_MAX_OPTIONS:
            raise ValueError("options must contain 1..20 items")
        seen: set[str] = set()
        for option in options:
            if not isinstance(option, ContextInteractionOption):
                raise ValueError("options must contain ContextInteractionOption items")
            if option.option_id in seen:
                raise ValueError("option_id values must be unique")
            seen.add(option.option_id)
        if not isinstance(self.allow_cancel, bool):
            raise ValueError("allow_cancel must be boolean")
        object.__setattr__(self, "options", options)


@dataclass(frozen=True)
class ContextInteractionResult:
    """Provider-neutral outcome of a bounded contextual interaction."""

    status: ContextInteractionStatus
    message: str | None = None

    def __post_init__(self) -> None:
        if self.status not in ("completed", "cancelled"):
            raise ValueError("status must be completed or cancelled")
        _require_optional_bounded_text(
            self.message,
            "message",
            max_length=CONTEXT_INTERACTION_MAX_RESULT_MESSAGE_LENGTH,
        )


def validate_context_interaction_workflow_ref(value: str) -> str:
    """Validate an opaque safe workflow reference used inside Mini App context claims."""

    _require_bounded_text(
        value,
        "workflow_ref",
        max_length=CONTEXT_INTERACTION_MAX_WORKFLOW_REF_LENGTH,
    )
    if not _CONTEXT_INTERACTION_WORKFLOW_REF_RE.fullmatch(value):
        raise ValueError("workflow_ref contains unsafe characters")
    return value


def _require_bounded_text(value: str, field_name: str, *, max_length: int) -> None:
    if not isinstance(value, str) or value == "" or len(value) > max_length:
        raise ValueError(f"{field_name} must be a non-empty string up to {max_length} chars")


def _require_optional_bounded_text(
    value: str | None,
    field_name: str,
    *,
    max_length: int,
) -> None:
    if value is None:
        return
    _require_bounded_text(value, field_name, max_length=max_length)


__all__ = [
    "ActiveKaitenConnectionSecret",
    "BindKaitenConnectionInput",
    "CONTEXT_INTERACTION_MAX_DESCRIPTION_LENGTH",
    "CONTEXT_INTERACTION_MAX_LABEL_LENGTH",
    "CONTEXT_INTERACTION_MAX_OPTION_ID_LENGTH",
    "CONTEXT_INTERACTION_MAX_OPTIONS",
    "CONTEXT_INTERACTION_MAX_PROMPT_LENGTH",
    "CONTEXT_INTERACTION_MAX_RESULT_MESSAGE_LENGTH",
    "CONTEXT_INTERACTION_MAX_TITLE_LENGTH",
    "CONTEXT_INTERACTION_MAX_WORKFLOW_REF_LENGTH",
    "CONTEXT_INTERACTION_WORKFLOW_REF_PATTERN",
    "ContextInteractionOption",
    "ContextInteractionResult",
    "ContextInteractionStatus",
    "ContextInteractionView",
    "EncryptedToken",
    "IdentityResolution",
    "KaitenConnectionResult",
    "KaitenConnectionStatus",
    "KaitenCredentialSnapshot",
    "KaitenCredentialVerification",
    "MarkKaitenNeedsReauthInput",
    "MaxChatType",
    "NotificationSettingsResult",
    "ResolveMaxIdentityInput",
    "UpdateNotificationSettingsInput",
    "UserStatus",
    "validate_context_interaction_workflow_ref",
]
