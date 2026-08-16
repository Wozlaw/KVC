"""Token cipher configuration tests."""

from __future__ import annotations

import json

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from kvc_config import AppSettings
from kvc_integrations.security import (
    VersionedFernetTokenCipher,
    build_token_cipher,
    parse_token_encryption_key_ring,
)


def generate_key() -> str:
    return Fernet.generate_key().decode("ascii")


def key_ring_json(keys: dict[str, str]) -> str:
    return json.dumps(keys, separators=(",", ":"))


def test_generic_settings_load_without_crypto_values() -> None:
    settings = AppSettings(_env_file=None)

    assert settings.token_encryption_active_version is None
    assert settings.token_encryption_keys is None


def test_settings_load_exact_frozen_environment_names(monkeypatch: pytest.MonkeyPatch) -> None:
    key = generate_key()
    monkeypatch.setenv("KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION", "1")
    monkeypatch.setenv("KVC_TOKEN_ENCRYPTION_KEYS", key_ring_json({"1": key}))

    settings = AppSettings(_env_file=None)

    assert settings.token_encryption_active_version == 1
    assert settings.token_encryption_keys is not None
    assert settings.token_encryption_keys.get_secret_value() == key_ring_json({"1": key})


def test_settings_repr_does_not_expose_key_json() -> None:
    key = generate_key()
    raw_json = key_ring_json({"1": key})
    settings = AppSettings(
        _env_file=None,
        token_encryption_active_version=1,
        token_encryption_keys=SecretStr(raw_json),
    )

    assert key not in repr(settings)
    assert raw_json not in repr(settings)
    assert key not in str(settings.token_encryption_keys)
    assert raw_json not in str(settings.token_encryption_keys)


def test_valid_single_version_config_builds_cipher() -> None:
    key = generate_key()
    settings = AppSettings(
        _env_file=None,
        token_encryption_active_version=1,
        token_encryption_keys=SecretStr(key_ring_json({"1": key})),
    )

    cipher = build_token_cipher(settings)
    encrypted = cipher.encrypt("token")

    assert isinstance(cipher, VersionedFernetTokenCipher)
    assert encrypted.version == 1
    assert cipher.decrypt(encrypted.ciphertext, encrypted.version) == "token"


def test_multi_version_rotation_config_builds_cipher() -> None:
    old_key = generate_key()
    new_key = generate_key()
    old_cipher = VersionedFernetTokenCipher(keys={1: old_key}, active_version=1)
    old_encrypted = old_cipher.encrypt("old-token")
    settings = AppSettings(
        _env_file=None,
        token_encryption_active_version=2,
        token_encryption_keys=SecretStr(key_ring_json({"1": old_key, "2": new_key})),
    )

    rotated_cipher = build_token_cipher(settings)
    new_encrypted = rotated_cipher.encrypt("new-token")

    assert new_encrypted.version == 2
    assert rotated_cipher.decrypt(old_encrypted.ciphertext, old_encrypted.version) == "old-token"
    assert rotated_cipher.decrypt(new_encrypted.ciphertext, new_encrypted.version) == "new-token"


@pytest.mark.parametrize(
    "settings",
    [
        AppSettings(
            _env_file=None,
            token_encryption_active_version=None,
            token_encryption_keys=SecretStr(key_ring_json({"1": generate_key()})),
        ),
        AppSettings(_env_file=None, token_encryption_active_version=1, token_encryption_keys=None),
    ],
)
def test_build_cipher_requires_complete_crypto_config(settings: AppSettings) -> None:
    with pytest.raises(ValueError):
        build_token_cipher(settings)


@pytest.mark.parametrize(
    "raw_json",
    [
        "not-json-SYNTHETIC-KEY-MUST-NOT-LEAK",
        "[]",
        '"scalar"',
        "{}",
        key_ring_json({"not-an-int": generate_key()}),
        key_ring_json({"0": generate_key()}),
        key_ring_json({"-1": generate_key()}),
        key_ring_json({"1": ""}),
        json.dumps({"1": 123}),
        key_ring_json({"1": "SYNTHETIC-KEY-MUST-NOT-LEAK"}),
    ],
)
def test_key_ring_parser_rejects_invalid_json_and_keys_safely(raw_json: str) -> None:
    with pytest.raises(ValueError) as error:
        parse_token_encryption_key_ring(SecretStr(raw_json))

    rendered_error = f"{error.value!s} {error.value!r}"
    assert "SYNTHETIC-KEY-MUST-NOT-LEAK" not in rendered_error


def test_key_ring_parser_rejects_normalized_version_collision() -> None:
    key = generate_key()

    with pytest.raises(ValueError, match="duplicate normalized versions"):
        parse_token_encryption_key_ring(SecretStr(f'{{"1":"{key}","01":"{key}"}}'))


def test_build_cipher_rejects_active_version_absent_from_map() -> None:
    settings = AppSettings(
        _env_file=None,
        token_encryption_active_version=2,
        token_encryption_keys=SecretStr(key_ring_json({"1": generate_key()})),
    )

    with pytest.raises(ValueError, match="Active credential encryption version"):
        build_token_cipher(settings)
