"""KaitenConnectionService orchestration tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import kvc_application.services.kaiten_connection as service_module
from kvc_application.dto import (
    BindKaitenConnectionInput,
    EncryptedToken,
    KaitenCredentialVerification,
)
from kvc_application.errors import CredentialEncryptionFailed, UserDisabled
from kvc_application.services.kaiten_connection import KaitenConnectionService


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None


class FakeSession:
    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None

    def begin(self) -> FakeTransaction:
        return FakeTransaction()


class FakeVerifier:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def verify(
        self,
        *,
        api_base_url: str,
        plaintext_token: str,
    ) -> KaitenCredentialVerification:
        self._events.append("verify")
        return KaitenCredentialVerification(kaiten_user_id="verified-user", workspace_id=None)


class FailingVerifier:
    async def verify(
        self,
        *,
        api_base_url: str,
        plaintext_token: str,
    ) -> KaitenCredentialVerification:
        raise AssertionError("verifier must not be called")


class FakeCipher:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def encrypt(self, plaintext: str) -> EncryptedToken:
        self._events.append("encrypt")
        return EncryptedToken(ciphertext=b"ciphertext", version=1)

    def decrypt(self, ciphertext: bytes, version: int) -> str:
        self._events.append("decrypt")
        return "plaintext"


class FailingCipher(FakeCipher):
    def encrypt(self, plaintext: str) -> EncryptedToken:
        self._events.append("encrypt")
        raise CredentialEncryptionFailed("synthetic encryption failure")


class FakeClock:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def now(self) -> datetime:
        self._events.append("clock")
        return datetime(2026, 8, 16, 12, tzinfo=UTC)


def fake_sessionmaker() -> FakeSession:
    return FakeSession()


@pytest.mark.asyncio
async def test_bind_verifies_and_encrypts_before_final_row_locks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    user_id = uuid.uuid4()

    class FakeUserRepository:
        def __init__(self, session: FakeSession) -> None:
            self._session = session

        async def get_by_id(self, requested_user_id: uuid.UUID) -> object:
            events.append("preflight_read")
            return SimpleNamespace(id=requested_user_id, status="ACTIVE")

        async def get_by_id_for_update(self, requested_user_id: uuid.UUID) -> object:
            events.append("user_lock")
            return SimpleNamespace(id=requested_user_id, status="ACTIVE")

    class FakeConnectionRepository:
        def __init__(self, session: FakeSession) -> None:
            self._session = session

        async def get_for_user_for_update(self, requested_user_id: uuid.UUID) -> None:
            events.append("connection_lock")
            return None

        async def create(self, **kwargs: object) -> object:
            events.append("write")
            return SimpleNamespace(
                id=uuid.uuid4(),
                user_id=kwargs["user_id"],
                status=kwargs["status"],
                api_base_url=kwargs["api_base_url"],
                kaiten_user_id=kwargs["kaiten_user_id"],
                workspace_id=kwargs["workspace_id"],
                encrypted_api_token=kwargs["encrypted_api_token"],
                token_encryption_version=kwargs["token_encryption_version"],
                last_verified_at=kwargs["last_verified_at"],
            )

    monkeypatch.setattr(service_module, "UserRepository", FakeUserRepository)
    monkeypatch.setattr(service_module, "KaitenConnectionRepository", FakeConnectionRepository)

    service = KaitenConnectionService(
        fake_sessionmaker,  # type: ignore[arg-type]
        FakeVerifier(events),
        FakeCipher(events),
        FakeClock(events),
    )

    result = await service.bind_or_replace_connection(
        BindKaitenConnectionInput(
            user_id=user_id,
            api_base_url="https://example.kaiten.ru/api/latest",
            plaintext_token="synthetic-token",
        )
    )

    assert result.status == "ACTIVE"
    assert events == [
        "preflight_read",
        "verify",
        "encrypt",
        "clock",
        "user_lock",
        "connection_lock",
        "write",
    ]


@pytest.mark.asyncio
async def test_disabled_preflight_rejects_before_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeUserRepository:
        def __init__(self, session: FakeSession) -> None:
            self._session = session

        async def get_by_id(self, requested_user_id: uuid.UUID) -> object:
            events.append("preflight_read")
            return SimpleNamespace(id=requested_user_id, status="DISABLED")

    monkeypatch.setattr(service_module, "UserRepository", FakeUserRepository)

    service = KaitenConnectionService(
        fake_sessionmaker,  # type: ignore[arg-type]
        FailingVerifier(),
        FakeCipher(events),
        FakeClock(events),
    )

    with pytest.raises(UserDisabled):
        await service.bind_or_replace_connection(
            BindKaitenConnectionInput(
                user_id=uuid.uuid4(),
                api_base_url="https://example.kaiten.ru/api/latest",
                plaintext_token="synthetic-token",
            )
        )

    assert events == ["preflight_read"]


@pytest.mark.asyncio
async def test_encryption_failure_happens_before_final_write_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeUserRepository:
        def __init__(self, session: FakeSession) -> None:
            self._session = session

        async def get_by_id(self, requested_user_id: uuid.UUID) -> object:
            events.append("preflight_read")
            return SimpleNamespace(id=requested_user_id, status="ACTIVE")

        async def get_by_id_for_update(self, requested_user_id: uuid.UUID) -> object:
            events.append("user_lock")
            return SimpleNamespace(id=requested_user_id, status="ACTIVE")

    monkeypatch.setattr(service_module, "UserRepository", FakeUserRepository)

    service = KaitenConnectionService(
        fake_sessionmaker,  # type: ignore[arg-type]
        FakeVerifier(events),
        FailingCipher(events),
        FakeClock(events),
    )

    with pytest.raises(CredentialEncryptionFailed):
        await service.bind_or_replace_connection(
            BindKaitenConnectionInput(
                user_id=uuid.uuid4(),
                api_base_url="https://example.kaiten.ru/api/latest",
                plaintext_token="synthetic-token",
            )
        )

    assert events == ["preflight_read", "verify", "encrypt"]
