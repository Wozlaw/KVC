"""IdentityService unit contract tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from kvc_application.dto import IdentityResolution, ResolveMaxIdentityInput
from kvc_application.errors import IdentityConflict, PersistenceConflict
from kvc_application.services.identity import IdentityService

USER_ID = UUID("00000000-0000-0000-0000-000000000101")
BINDING_ID = UUID("00000000-0000-0000-0000-000000000102")


def synthetic_input() -> ResolveMaxIdentityInput:
    return ResolveMaxIdentityInput(
        max_user_id="synthetic-max-user",
        max_chat_id="synthetic-max-chat",
        chat_type="PRIVATE",
    )


def synthetic_resolution(*, is_new_user: bool) -> IdentityResolution:
    return IdentityResolution(
        user_id=USER_ID,
        max_chat_binding_id=BINDING_ID,
        user_status="ACTIVE",
        is_new_user=is_new_user,
        kaiten_connection_status=None,
    )


def synthetic_integrity_error() -> IntegrityError:
    return IntegrityError("synthetic statement", {}, Exception("synthetic integrity"))


@dataclass
class RetryProbeIdentityService(IdentityService):
    outcomes: list[IdentityResolution | BaseException]

    def __init__(self, outcomes: list[IdentityResolution | BaseException]) -> None:
        self.outcomes = outcomes
        self.allow_onboarding_values: list[bool] = []

    async def _resolve_once(
        self,
        input: ResolveMaxIdentityInput,
        *,
        allow_onboarding: bool,
    ) -> IdentityResolution:
        self.allow_onboarding_values.append(allow_onboarding)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


async def test_integrity_error_retries_once_as_existing_identity() -> None:
    service = RetryProbeIdentityService(
        [
            synthetic_integrity_error(),
            synthetic_resolution(is_new_user=False),
        ]
    )

    result = await service.resolve_or_onboard_private_max_user(synthetic_input())

    assert result.is_new_user is False
    assert service.allow_onboarding_values == [True, False]


async def test_second_integrity_error_maps_to_persistence_conflict() -> None:
    service = RetryProbeIdentityService(
        [
            synthetic_integrity_error(),
            synthetic_integrity_error(),
        ]
    )

    with pytest.raises(PersistenceConflict):
        await service.resolve_or_onboard_private_max_user(synthetic_input())

    assert service.allow_onboarding_values == [True, False]


async def test_identity_conflict_is_not_retried_or_swallowed() -> None:
    service = RetryProbeIdentityService([IdentityConflict("synthetic conflict")])

    with pytest.raises(IdentityConflict):
        await service.resolve_or_onboard_private_max_user(synthetic_input())

    assert service.allow_onboarding_values == [True]


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> bool | None:
        return None


class FakeSession:
    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> bool | None:
        return None

    def begin(self) -> FakeTransaction:
        return FakeTransaction()


@asynccontextmanager
async def fake_sessionmaker() -> AsyncIterator[FakeSession]:
    yield FakeSession()


class FakeBinding:
    id = BINDING_ID
    user_id = USER_ID
    max_user_id = "synthetic-max-user"
    max_chat_id = "synthetic-max-chat"
    chat_type = "PRIVATE"
    is_primary = True


class MissingUserRepository:
    def __init__(self, session: FakeSession) -> None:
        pass

    async def get_by_id(self, user_id: UUID) -> None:
        return None


class ExistingChatRepository:
    def __init__(self, session: FakeSession) -> None:
        pass

    async def get_by_max_chat_id(self, max_chat_id: str) -> FakeBinding:
        return FakeBinding()


class UnusedNotificationSettingsRepository:
    def __init__(self, session: FakeSession) -> None:
        pass


class UnusedKaitenConnectionRepository:
    def __init__(self, session: FakeSession) -> None:
        pass


async def test_missing_user_for_existing_binding_maps_to_persistence_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import kvc_application.services.identity as identity_module

    monkeypatch.setattr(identity_module, "UserRepository", MissingUserRepository)
    monkeypatch.setattr(identity_module, "MaxChatRepository", ExistingChatRepository)
    monkeypatch.setattr(
        identity_module,
        "NotificationSettingsRepository",
        UnusedNotificationSettingsRepository,
    )
    monkeypatch.setattr(
        identity_module,
        "KaitenConnectionRepository",
        UnusedKaitenConnectionRepository,
    )
    service = IdentityService(fake_sessionmaker)

    with pytest.raises(PersistenceConflict):
        await service.resolve_or_onboard_private_max_user(synthetic_input())
