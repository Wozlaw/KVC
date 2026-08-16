"""Application-layer provider-neutral ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from kvc_application.dto import (
    ContextInteractionResult,
    ContextInteractionView,
    EncryptedToken,
    KaitenCredentialVerification,
)


class TokenCipher(Protocol):
    """Encrypt and decrypt Kaiten API tokens through an injected adapter."""

    def encrypt(self, plaintext: str) -> EncryptedToken: ...

    def decrypt(self, ciphertext: bytes, version: int) -> str: ...


class KaitenCredentialVerifier(Protocol):
    """Verify Kaiten credentials through an injected adapter."""

    async def verify(
        self,
        *,
        api_base_url: str,
        plaintext_token: str,
    ) -> KaitenCredentialVerification: ...


class Clock(Protocol):
    """Clock contract for timezone-aware UTC timestamps."""

    def now(self) -> datetime: ...


class ContextInteractionResolver(Protocol):
    """Application-facing resolver for bounded contextual single-choice flows."""

    async def get_interaction(
        self,
        *,
        user_id: UUID,
        workflow_ref: str,
    ) -> ContextInteractionView: ...

    async def submit_selection(
        self,
        *,
        user_id: UUID,
        workflow_ref: str,
        option_id: str,
    ) -> ContextInteractionResult: ...

    async def cancel_interaction(
        self,
        *,
        user_id: UUID,
        workflow_ref: str,
    ) -> ContextInteractionResult: ...


__all__ = [
    "Clock",
    "ContextInteractionResolver",
    "KaitenCredentialVerifier",
    "TokenCipher",
]
