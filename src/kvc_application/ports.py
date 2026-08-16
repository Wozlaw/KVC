"""Application-layer provider-neutral ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from kvc_application.dto import EncryptedToken, KaitenCredentialVerification


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


__all__ = [
    "Clock",
    "KaitenCredentialVerifier",
    "TokenCipher",
]
