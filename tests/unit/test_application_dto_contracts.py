"""Application DTO contract tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import UTC, datetime
from typing import get_args
from uuid import UUID

import pytest

from kvc_application.dto import (
    ActiveKaitenConnectionSecret,
    BindKaitenConnectionInput,
    EncryptedToken,
    IdentityResolution,
    KaitenConnectionResult,
    KaitenConnectionStatus,
    KaitenCredentialSnapshot,
    KaitenCredentialVerification,
    MarkKaitenNeedsReauthInput,
    MaxChatType,
    ResolveMaxIdentityInput,
    UserStatus,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
BINDING_ID = UUID("00000000-0000-0000-0000-000000000002")
CONNECTION_ID = UUID("00000000-0000-0000-0000-000000000003")
FAKE_TOKEN = "test-token-do-not-use"
FAKE_CIPHERTEXT = b"test-ciphertext-do-not-use"


def field_names(dto_type: type[object]) -> list[str]:
    return [field.name for field in fields(dto_type)]


def test_status_type_aliases_are_literal_contracts() -> None:
    assert get_args(MaxChatType) == ("PRIVATE",)
    assert get_args(UserStatus) == ("ACTIVE", "DISABLED")
    assert get_args(KaitenConnectionStatus) == ("ACTIVE", "DISABLED", "NEEDS_REAUTH")


@pytest.mark.parametrize(
    ("dto_type", "expected_fields"),
    [
        (ResolveMaxIdentityInput, ["max_user_id", "max_chat_id", "chat_type"]),
        (
            IdentityResolution,
            [
                "user_id",
                "max_chat_binding_id",
                "user_status",
                "is_new_user",
                "kaiten_connection_status",
            ],
        ),
        (BindKaitenConnectionInput, ["user_id", "api_base_url", "plaintext_token"]),
        (
            KaitenConnectionResult,
            [
                "connection_id",
                "user_id",
                "status",
                "api_base_url",
                "kaiten_user_id",
                "workspace_id",
                "last_verified_at",
            ],
        ),
        (
            KaitenCredentialSnapshot,
            ["connection_id", "encrypted_api_token", "token_encryption_version"],
        ),
        (
            ActiveKaitenConnectionSecret,
            ["connection_id", "user_id", "api_base_url", "plaintext_token", "snapshot"],
        ),
        (MarkKaitenNeedsReauthInput, ["user_id", "snapshot", "reason"]),
        (KaitenCredentialVerification, ["kaiten_user_id", "workspace_id"]),
        (EncryptedToken, ["ciphertext", "version"]),
    ],
)
def test_dto_field_inventory(dto_type: type[object], expected_fields: list[str]) -> None:
    assert is_dataclass(dto_type)
    assert field_names(dto_type) == expected_fields


@pytest.mark.parametrize(
    "dto",
    [
        ResolveMaxIdentityInput("max-user", "max-chat", "PRIVATE"),
        IdentityResolution(USER_ID, BINDING_ID, "ACTIVE", False, "NEEDS_REAUTH"),
        BindKaitenConnectionInput(USER_ID, "https://kaiten.example", FAKE_TOKEN),
        KaitenConnectionResult(
            CONNECTION_ID,
            USER_ID,
            "ACTIVE",
            "https://kaiten.example",
            "kaiten-user",
            "workspace",
            datetime(2026, 8, 16, tzinfo=UTC),
        ),
        KaitenCredentialSnapshot(CONNECTION_ID, FAKE_CIPHERTEXT, 1),
        ActiveKaitenConnectionSecret(
            CONNECTION_ID,
            USER_ID,
            "https://kaiten.example",
            FAKE_TOKEN,
            KaitenCredentialSnapshot(CONNECTION_ID, FAKE_CIPHERTEXT, 1),
        ),
        MarkKaitenNeedsReauthInput(
            USER_ID,
            KaitenCredentialSnapshot(CONNECTION_ID, FAKE_CIPHERTEXT, 1),
            "synthetic-auth-failure",
        ),
        KaitenCredentialVerification("kaiten-user", "workspace"),
        EncryptedToken(FAKE_CIPHERTEXT, 1),
    ],
)
def test_dtos_are_frozen(dto: object) -> None:
    first_field_name = fields(dto)[0].name

    with pytest.raises(FrozenInstanceError):
        setattr(dto, first_field_name, "blocked")


def test_bind_kaiten_connection_input_hides_plaintext_token_from_repr() -> None:
    dto = BindKaitenConnectionInput(USER_ID, "https://kaiten.example", FAKE_TOKEN)

    assert FAKE_TOKEN not in repr(dto)


def test_active_kaiten_connection_secret_hides_plaintext_and_snapshot_from_repr() -> None:
    snapshot = KaitenCredentialSnapshot(CONNECTION_ID, FAKE_CIPHERTEXT, 1)
    dto = ActiveKaitenConnectionSecret(
        CONNECTION_ID,
        USER_ID,
        "https://kaiten.example",
        FAKE_TOKEN,
        snapshot,
    )
    rendered = repr(dto)

    assert FAKE_TOKEN not in rendered
    assert "KaitenCredentialSnapshot" not in rendered
    assert FAKE_CIPHERTEXT.decode("ascii") not in rendered


def test_kaiten_credential_snapshot_hides_ciphertext_from_repr() -> None:
    dto = KaitenCredentialSnapshot(CONNECTION_ID, FAKE_CIPHERTEXT, 1)

    assert FAKE_CIPHERTEXT.decode("ascii") not in repr(dto)


def test_encrypted_token_hides_ciphertext_from_repr() -> None:
    dto = EncryptedToken(FAKE_CIPHERTEXT, 1)

    assert FAKE_CIPHERTEXT.decode("ascii") not in repr(dto)


def test_mark_needs_reauth_input_hides_snapshot_and_reason_from_repr() -> None:
    snapshot = KaitenCredentialSnapshot(CONNECTION_ID, FAKE_CIPHERTEXT, 1)
    dto = MarkKaitenNeedsReauthInput(USER_ID, snapshot, "synthetic-auth-failure")
    rendered = repr(dto)

    assert "KaitenCredentialSnapshot" not in rendered
    assert "synthetic-auth-failure" not in rendered
    assert FAKE_CIPHERTEXT.decode("ascii") not in rendered
