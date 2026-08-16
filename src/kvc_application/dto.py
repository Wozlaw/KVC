"""Application-layer data transfer contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

MaxChatType = Literal["PRIVATE"]
UserStatus = Literal["ACTIVE", "DISABLED"]
KaitenConnectionStatus = Literal["ACTIVE", "DISABLED", "NEEDS_REAUTH"]


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


__all__ = [
    "ActiveKaitenConnectionSecret",
    "BindKaitenConnectionInput",
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
]
