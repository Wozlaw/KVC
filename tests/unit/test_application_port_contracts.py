"""Application port contract tests."""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import get_type_hints

from kvc_application import (
    ActiveKaitenConnectionSecret,
    ApplicationError,
    BindKaitenConnectionInput,
    Clock,
    EncryptedToken,
    IdentityConflict,
    IdentityResolution,
    KaitenConnectionResult,
    KaitenConnectionStatus,
    KaitenCredentialSnapshot,
    KaitenCredentialVerification,
    KaitenCredentialVerifier,
    MarkKaitenNeedsReauthInput,
    MaxChatType,
    ResolveMaxIdentityInput,
    TokenCipher,
    UserStatus,
)
from kvc_application.ports import Clock as ClockPort
from kvc_application.ports import KaitenCredentialVerifier as KaitenCredentialVerifierPort
from kvc_application.ports import TokenCipher as TokenCipherPort


def test_application_contracts_import_from_package_root() -> None:
    assert ActiveKaitenConnectionSecret
    assert ApplicationError
    assert BindKaitenConnectionInput
    assert Clock
    assert EncryptedToken
    assert IdentityConflict
    assert IdentityResolution
    assert KaitenConnectionResult
    assert KaitenConnectionStatus
    assert KaitenCredentialSnapshot
    assert KaitenCredentialVerification
    assert KaitenCredentialVerifier
    assert MarkKaitenNeedsReauthInput
    assert MaxChatType
    assert ResolveMaxIdentityInput
    assert TokenCipher
    assert UserStatus


def test_port_inventory() -> None:
    assert TokenCipherPort
    assert KaitenCredentialVerifierPort
    assert ClockPort


def test_token_cipher_signatures_are_sync_and_provider_neutral() -> None:
    encrypt_signature = inspect.signature(TokenCipherPort.encrypt)
    decrypt_signature = inspect.signature(TokenCipherPort.decrypt)
    encrypt_hints = get_type_hints(TokenCipherPort.encrypt)
    decrypt_hints = get_type_hints(TokenCipherPort.decrypt)

    assert not inspect.iscoroutinefunction(TokenCipherPort.encrypt)
    assert not inspect.iscoroutinefunction(TokenCipherPort.decrypt)
    assert list(encrypt_signature.parameters) == ["self", "plaintext"]
    assert encrypt_hints["plaintext"] is str
    assert encrypt_hints["return"] is EncryptedToken
    assert list(decrypt_signature.parameters) == ["self", "ciphertext", "version"]
    assert decrypt_hints["ciphertext"] is bytes
    assert decrypt_hints["version"] is int
    assert decrypt_hints["return"] is str


def test_kaiten_credential_verifier_signature_is_async_keyword_only() -> None:
    signature = inspect.signature(KaitenCredentialVerifierPort.verify)
    hints = get_type_hints(KaitenCredentialVerifierPort.verify)

    assert inspect.iscoroutinefunction(KaitenCredentialVerifierPort.verify)
    assert list(signature.parameters) == ["self", "api_base_url", "plaintext_token"]
    assert signature.parameters["api_base_url"].kind is inspect.Parameter.KEYWORD_ONLY
    assert hints["api_base_url"] is str
    assert signature.parameters["plaintext_token"].kind is inspect.Parameter.KEYWORD_ONLY
    assert hints["plaintext_token"] is str
    assert hints["return"] is KaitenCredentialVerification


def test_clock_signature_is_sync() -> None:
    signature = inspect.signature(ClockPort.now)
    hints = get_type_hints(ClockPort.now)

    assert not inspect.iscoroutinefunction(ClockPort.now)
    assert list(signature.parameters) == ["self"]
    assert hints["return"] is datetime
