"""Versioned Fernet token cipher tests."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet, InvalidToken

from kvc_application.dto import EncryptedToken
from kvc_application.errors import CredentialDecryptionFailed, CredentialEncryptionFailed
from kvc_application.ports import TokenCipher
from kvc_integrations.security import VersionedFernetTokenCipher


def generate_key() -> str:
    return Fernet.generate_key().decode("ascii")


def make_cipher(
    *,
    keys: dict[int, str] | None = None,
    active_version: int = 1,
) -> VersionedFernetTokenCipher:
    return VersionedFernetTokenCipher(
        keys=keys if keys is not None else {active_version: generate_key()},
        active_version=active_version,
    )


@pytest.mark.parametrize(
    "plaintext",
    [
        "ascii-token",
        "кириллический-токен",
        "unicode-token-漢字-🙂",
    ],
)
def test_encrypt_decrypt_round_trips_utf8_plaintext(plaintext: str) -> None:
    cipher = make_cipher()

    encrypted = cipher.encrypt(plaintext)

    assert isinstance(encrypted, EncryptedToken)
    assert encrypted.version == 1
    assert encrypted.ciphertext != plaintext.encode("utf-8")
    assert cipher.decrypt(encrypted.ciphertext, encrypted.version) == plaintext


def test_encrypt_always_uses_active_version() -> None:
    cipher = make_cipher(keys={1: generate_key(), 2: generate_key()}, active_version=2)

    encrypted = cipher.encrypt("token")

    assert encrypted.version == 2


def test_old_version_remains_decryptable_after_active_version_changes() -> None:
    keys = {1: generate_key(), 2: generate_key()}
    old_cipher = make_cipher(keys=keys, active_version=1)
    rotated_cipher = make_cipher(keys=keys, active_version=2)

    old_encrypted = old_cipher.encrypt("old-token")
    new_encrypted = rotated_cipher.encrypt("new-token")

    assert old_encrypted.version == 1
    assert new_encrypted.version == 2
    assert rotated_cipher.decrypt(old_encrypted.ciphertext, old_encrypted.version) == "old-token"
    assert rotated_cipher.decrypt(new_encrypted.ciphertext, new_encrypted.version) == "new-token"


def test_decrypt_unknown_version_fails_safely() -> None:
    cipher = make_cipher()

    with pytest.raises(
        CredentialDecryptionFailed, match="Unsupported credential encryption version"
    ):
        cipher.decrypt(b"synthetic-ciphertext", 2)


def test_decrypt_wrong_key_for_same_version_fails_safely() -> None:
    first = make_cipher(keys={1: generate_key()}, active_version=1)
    second = make_cipher(keys={1: generate_key()}, active_version=1)
    encrypted = first.encrypt("SYNTHETIC-PLAINTEXT-MUST-NOT-LEAK")

    with pytest.raises(CredentialDecryptionFailed) as error:
        second.decrypt(encrypted.ciphertext, encrypted.version)

    rendered_error = f"{error.value!s} {error.value!r}"
    assert "SYNTHETIC-PLAINTEXT-MUST-NOT-LEAK" not in rendered_error
    assert encrypted.ciphertext.decode("ascii") not in rendered_error


def test_decrypt_tampered_ciphertext_fails_safely() -> None:
    cipher = make_cipher()
    encrypted = cipher.encrypt("token")
    tampered = encrypted.ciphertext[:-1] + b"A"

    with pytest.raises(CredentialDecryptionFailed):
        cipher.decrypt(tampered, encrypted.version)


def test_decrypt_invalid_utf8_plaintext_fails_safely() -> None:
    key = generate_key()
    token = Fernet(key.encode("ascii")).encrypt(b"\xff\xfe")
    cipher = make_cipher(keys={1: key}, active_version=1)

    with pytest.raises(CredentialDecryptionFailed, match="not valid UTF-8"):
        cipher.decrypt(token, 1)


def test_input_key_mapping_mutation_does_not_change_adapter() -> None:
    original_key = generate_key()
    replacement_key = generate_key()
    keys = {1: original_key}
    cipher = make_cipher(keys=keys, active_version=1)

    keys[1] = replacement_key
    encrypted = cipher.encrypt("token")

    assert Fernet(original_key.encode("ascii")).decrypt(encrypted.ciphertext) == b"token"
    with pytest.raises(InvalidToken):
        Fernet(replacement_key.encode("ascii")).decrypt(encrypted.ciphertext)


def test_adapter_repr_does_not_reveal_key_material() -> None:
    key = generate_key()
    cipher = make_cipher(keys={1: key}, active_version=1)

    assert key not in repr(cipher)
    assert key not in str(cipher)


def test_decryption_error_does_not_reveal_ciphertext_marker() -> None:
    cipher = make_cipher()
    ciphertext = b"SYNTHETIC-CIPHERTEXT-MUST-NOT-LEAK"

    with pytest.raises(CredentialDecryptionFailed) as error:
        cipher.decrypt(ciphertext, 1)

    rendered_error = f"{error.value!s} {error.value!r}"
    assert "SYNTHETIC-CIPHERTEXT-MUST-NOT-LEAK" not in rendered_error


def test_encryption_error_does_not_reveal_plaintext() -> None:
    class FailingFernet:
        def encrypt(self, data: bytes) -> bytes:
            raise ValueError("synthetic encryption failure")

    cipher = make_cipher()
    cipher._fernets[1] = FailingFernet()  # type: ignore[assignment]  # noqa: SLF001

    with pytest.raises(CredentialEncryptionFailed) as error:
        cipher.encrypt("SYNTHETIC-PLAINTEXT-MUST-NOT-LEAK")

    rendered_error = f"{error.value!s} {error.value!r}"
    assert "SYNTHETIC-PLAINTEXT-MUST-NOT-LEAK" not in rendered_error


@pytest.mark.parametrize(
    ("keys", "active_version"),
    [
        ({}, 1),
        ({1: generate_key()}, 0),
        ({1: generate_key()}, -1),
        ({1: generate_key()}, True),
        ({1: generate_key()}, 2),
        ({0: generate_key()}, 0),
        ({-1: generate_key()}, -1),
        ({True: generate_key()}, True),
        ({"1": generate_key()}, 1),
        ({1: "not-a-fernet-key"}, 1),
    ],
)
def test_constructor_rejects_invalid_key_ring(
    keys: dict[object, str],
    active_version: object,
) -> None:
    with pytest.raises(ValueError):
        VersionedFernetTokenCipher(keys=keys, active_version=active_version)  # type: ignore[arg-type]


def test_constructor_rejects_empty_key_string() -> None:
    with pytest.raises(ValueError):
        VersionedFernetTokenCipher(keys={1: ""}, active_version=1)


def test_structural_token_cipher_contract_is_usable() -> None:
    def decrypt_round_trip(token_cipher: TokenCipher) -> str:
        encrypted = token_cipher.encrypt("token")
        return token_cipher.decrypt(encrypted.ciphertext, encrypted.version)

    cipher = make_cipher()

    assert isinstance(cipher.encrypt("token"), EncryptedToken)
    assert decrypt_round_trip(cipher) == "token"
    assert callable(cipher.encrypt)
    assert callable(cipher.decrypt)
