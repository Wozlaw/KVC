"""Versioned Fernet TokenCipher adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, NewType, cast

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from kvc_application.dto import EncryptedToken
from kvc_application.errors import CredentialDecryptionFailed, CredentialEncryptionFailed
from kvc_config import AppSettings

_JsonObjectPairs = NewType("_JsonObjectPairs", list[tuple[str, Any]])


class VersionedFernetTokenCipher:
    """TokenCipher adapter backed by exact-version Fernet keys."""

    def __init__(
        self,
        *,
        keys: Mapping[int, str | bytes],
        active_version: int,
    ) -> None:
        normalized_keys = _build_fernet_key_ring(keys)
        if not normalized_keys:
            raise ValueError("Credential encryption key ring must not be empty")
        if _is_invalid_version(active_version):
            raise ValueError("Active credential encryption version must be a positive integer")
        if active_version not in normalized_keys:
            raise ValueError("Active credential encryption version is not configured")

        self._fernets = dict(normalized_keys)
        self._active_version = active_version

    def encrypt(self, plaintext: str) -> EncryptedToken:
        try:
            ciphertext = self._fernets[self._active_version].encrypt(plaintext.encode("utf-8"))
        except Exception as exc:
            raise CredentialEncryptionFailed("Failed to encrypt credential") from exc

        return EncryptedToken(ciphertext=ciphertext, version=self._active_version)

    def decrypt(self, ciphertext: bytes, version: int) -> str:
        if _is_invalid_version(version):
            raise CredentialDecryptionFailed("Unsupported credential encryption version")

        fernet = self._fernets.get(version)
        if fernet is None:
            raise CredentialDecryptionFailed("Unsupported credential encryption version")

        try:
            plaintext_bytes = fernet.decrypt(ciphertext)
        except InvalidToken as exc:
            raise CredentialDecryptionFailed("Failed to decrypt credential") from exc

        try:
            return plaintext_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CredentialDecryptionFailed("Decrypted credential is not valid UTF-8") from exc


def build_token_cipher(settings: AppSettings) -> VersionedFernetTokenCipher:
    """Build the production token cipher from secret-aware application settings."""

    if settings.token_encryption_active_version is None:
        raise ValueError("KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION is required to build TokenCipher")
    if settings.token_encryption_keys is None:
        raise ValueError("KVC_TOKEN_ENCRYPTION_KEYS is required to build TokenCipher")

    return VersionedFernetTokenCipher(
        keys=parse_token_encryption_key_ring(settings.token_encryption_keys),
        active_version=settings.token_encryption_active_version,
    )


def parse_token_encryption_key_ring(value: SecretStr | str | None) -> dict[int, str]:
    """Parse a secret JSON object into a validated Fernet key ring."""

    if value is None:
        raise ValueError("KVC_TOKEN_ENCRYPTION_KEYS is required to build TokenCipher")

    raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
    if raw_value == "":
        raise ValueError("KVC_TOKEN_ENCRYPTION_KEYS is required to build TokenCipher")

    try:
        parsed = json.loads(raw_value, object_pairs_hook=_JsonObjectPairs)
    except json.JSONDecodeError as exc:
        raise ValueError("KVC_TOKEN_ENCRYPTION_KEYS must be a JSON object") from exc

    if not isinstance(parsed, list) or not all(_is_json_pair(pair) for pair in parsed):
        raise ValueError("KVC_TOKEN_ENCRYPTION_KEYS must be a JSON object")

    key_ring: dict[int, str] = {}
    version_labels: dict[int, str] = {}
    for raw_version, raw_key in cast(_JsonObjectPairs, parsed):
        version = _parse_json_version(raw_version)
        existing_label = version_labels.get(version)
        if existing_label is not None and existing_label != raw_version:
            raise ValueError("KVC_TOKEN_ENCRYPTION_KEYS contains duplicate normalized versions")
        if not isinstance(raw_key, str) or raw_key == "":
            raise ValueError("KVC_TOKEN_ENCRYPTION_KEYS must map versions to Fernet key strings")

        key_ring[version] = raw_key
        version_labels[version] = raw_version

    if not key_ring:
        raise ValueError("KVC_TOKEN_ENCRYPTION_KEYS must not be empty")

    _build_fernet_key_ring(key_ring)
    return key_ring


def _build_fernet_key_ring(keys: Mapping[int, str | bytes]) -> dict[int, Fernet]:
    fernets: dict[int, Fernet] = {}
    for version, raw_key in keys.items():
        if _is_invalid_version(version):
            raise ValueError("Credential encryption versions must be positive integers")
        key = _normalize_fernet_key(raw_key)
        try:
            fernets[version] = Fernet(key)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid Fernet key for credential encryption") from exc
    return fernets


def _normalize_fernet_key(raw_key: str | bytes) -> bytes:
    if isinstance(raw_key, str):
        if raw_key == "":
            raise ValueError("Fernet key must not be empty")
        return raw_key.encode("ascii")
    if isinstance(raw_key, bytes):
        if raw_key == b"":
            raise ValueError("Fernet key must not be empty")
        return raw_key
    raise ValueError("Fernet key must be a string or bytes")


def _parse_json_version(raw_version: str) -> int:
    try:
        version = int(raw_version)
    except ValueError as exc:
        raise ValueError("KVC_TOKEN_ENCRYPTION_KEYS contains a non-integer version") from exc

    if version <= 0:
        raise ValueError("KVC_TOKEN_ENCRYPTION_KEYS versions must be positive integers")
    return version


def _is_invalid_version(version: object) -> bool:
    return not isinstance(version, int) or isinstance(version, bool) or version <= 0


def _is_json_pair(value: object) -> bool:
    return isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str)
