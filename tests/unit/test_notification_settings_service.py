"""NotificationSettingsService orchestration tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

import kvc_application.services.notification_settings as service_module
from kvc_application.dto import NotificationSettingsResult, UpdateNotificationSettingsInput
from kvc_application.errors import InvalidNotificationSettings, PersistenceConflict, UserDisabled
from kvc_application.services.notification_settings import NotificationSettingsService

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000701")
DEFAULT_SETTINGS = object()


class FakeTransaction:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def __aenter__(self) -> None:
        self._events.append("begin")
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        self._events.append("rollback" if exc_type is not None else "commit")


class FakeSession:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None

    def begin(self) -> FakeTransaction:
        return FakeTransaction(self._events)


def sessionmaker(events: list[str]) -> object:
    @asynccontextmanager
    async def _sessionmaker() -> AsyncIterator[FakeSession]:
        yield FakeSession(events)

    return _sessionmaker


def settings(
    *,
    enabled: bool = False,
    due_soon_days: int = 1,
    timezone: str = "UTC",
) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=USER_ID,
        enabled=enabled,
        due_soon_days=due_soon_days,
        timezone=timezone,
    )


def install_repositories(
    monkeypatch: pytest.MonkeyPatch,
    *,
    events: list[str],
    user_status: str = "ACTIVE",
    settings_row: SimpleNamespace | None | object = DEFAULT_SETTINGS,
    update_exc: Exception | None = None,
) -> None:
    row = settings() if settings_row is DEFAULT_SETTINGS else settings_row

    class FakeUserRepository:
        def __init__(self, session: FakeSession) -> None:
            self._session = session

        async def get_by_id(self, user_id: uuid.UUID) -> SimpleNamespace:
            events.append("user_read")
            return SimpleNamespace(id=user_id, status=user_status)

        async def get_by_id_for_update(self, user_id: uuid.UUID) -> SimpleNamespace:
            events.append("user_lock")
            return SimpleNamespace(id=user_id, status=user_status)

    class FakeNotificationSettingsRepository:
        def __init__(self, session: FakeSession) -> None:
            self._session = session

        async def get_for_user(self, user_id: uuid.UUID) -> SimpleNamespace | None:
            events.append("settings_read")
            return row

        async def get_for_user_for_update(self, user_id: uuid.UUID) -> SimpleNamespace | None:
            events.append("settings_lock")
            return row

        async def update_settings(
            self,
            current: SimpleNamespace,
            *,
            enabled: bool,
            due_soon_days: int,
            timezone: str,
        ) -> SimpleNamespace:
            events.append("settings_write")
            if update_exc is not None:
                raise update_exc
            current.enabled = enabled
            current.due_soon_days = due_soon_days
            current.timezone = timezone
            return current

    monkeypatch.setattr(service_module, "UserRepository", FakeUserRepository)
    monkeypatch.setattr(
        service_module,
        "NotificationSettingsRepository",
        FakeNotificationSettingsRepository,
    )


@pytest.mark.asyncio
async def test_get_valid_settings_returns_provider_neutral_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    install_repositories(
        monkeypatch,
        events=events,
        settings_row=settings(enabled=True, due_soon_days=3, timezone="Europe/Warsaw"),
    )
    service = NotificationSettingsService(sessionmaker(events))  # type: ignore[arg-type]

    result = await service.get_settings(USER_ID)

    assert result == NotificationSettingsResult(USER_ID, True, 3, "Europe/Warsaw")
    assert events == ["begin", "user_read", "settings_read", "commit"]


@pytest.mark.parametrize(
    "input",
    [
        UpdateNotificationSettingsInput(USER_ID, True, 1, "UTC"),
        UpdateNotificationSettingsInput(USER_ID, False, 5, "UTC"),
        UpdateNotificationSettingsInput(USER_ID, False, 1, "Asia/Tokyo"),
        UpdateNotificationSettingsInput(USER_ID, True, 30, " Europe/Moscow "),
        UpdateNotificationSettingsInput(USER_ID, True, 0, "UTC"),
    ],
)
@pytest.mark.asyncio
async def test_update_valid_settings(
    input: UpdateNotificationSettingsInput, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    install_repositories(monkeypatch, events=events)
    service = NotificationSettingsService(sessionmaker(events))  # type: ignore[arg-type]

    result = await service.update_settings(input)

    assert result.enabled is input.enabled
    assert result.due_soon_days == input.due_soon_days
    assert result.timezone == input.timezone.strip()
    assert events == ["begin", "user_lock", "settings_lock", "settings_write", "commit"]


@pytest.mark.parametrize(
    "input",
    [
        UpdateNotificationSettingsInput(USER_ID, True, -1, "UTC"),
        UpdateNotificationSettingsInput(USER_ID, True, 31, "UTC"),
        UpdateNotificationSettingsInput(USER_ID, True, 1.5, "UTC"),  # type: ignore[arg-type]
        UpdateNotificationSettingsInput(USER_ID, True, "3", "UTC"),  # type: ignore[arg-type]
        UpdateNotificationSettingsInput(USER_ID, "yes", 3, "UTC"),  # type: ignore[arg-type]
        UpdateNotificationSettingsInput(USER_ID, True, 3, ""),
        UpdateNotificationSettingsInput(USER_ID, True, 3, "No/Such_Zone"),
    ],
)
@pytest.mark.asyncio
async def test_invalid_settings_are_rejected_before_transaction(
    input: UpdateNotificationSettingsInput,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    install_repositories(monkeypatch, events=events)
    service = NotificationSettingsService(sessionmaker(events))  # type: ignore[arg-type]

    with pytest.raises(InvalidNotificationSettings):
        await service.update_settings(input)

    assert events == []


@pytest.mark.parametrize("operation", ["get", "update"])
@pytest.mark.asyncio
async def test_disabled_user_is_blocked(
    operation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    install_repositories(monkeypatch, events=events, user_status="DISABLED")
    service = NotificationSettingsService(sessionmaker(events))  # type: ignore[arg-type]

    with pytest.raises(UserDisabled):
        if operation == "get":
            await service.get_settings(USER_ID)
        else:
            await service.update_settings(UpdateNotificationSettingsInput(USER_ID, True, 3, "UTC"))


@pytest.mark.parametrize("operation", ["get", "update"])
@pytest.mark.asyncio
async def test_missing_settings_row_is_persistence_conflict(
    operation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    install_repositories(monkeypatch, events=events, settings_row=None)
    service = NotificationSettingsService(sessionmaker(events))  # type: ignore[arg-type]

    with pytest.raises(PersistenceConflict):
        if operation == "get":
            await service.get_settings(USER_ID)
        else:
            await service.update_settings(UpdateNotificationSettingsInput(USER_ID, True, 3, "UTC"))


@pytest.mark.asyncio
async def test_transaction_rolls_back_on_persistence_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    install_repositories(
        monkeypatch,
        events=events,
        update_exc=RuntimeError("synthetic persistence failure"),
    )
    service = NotificationSettingsService(sessionmaker(events))  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="synthetic persistence failure"):
        await service.update_settings(UpdateNotificationSettingsInput(USER_ID, True, 3, "UTC"))

    assert events == ["begin", "user_lock", "settings_lock", "settings_write", "rollback"]


def test_notification_settings_service_has_no_provider_imports() -> None:
    source = Path("src/kvc_application/services/notification_settings.py").read_text(
        encoding="utf-8"
    )

    assert "fastapi" not in source.lower()
    assert "httpx" not in source.lower()
    assert "kvc_integrations.max" not in source
