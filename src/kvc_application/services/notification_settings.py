"""Provider-neutral notification settings service."""

from __future__ import annotations

from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kvc_application.dto import (
    NotificationSettingsResult,
    UpdateNotificationSettingsInput,
    UserStatus,
)
from kvc_application.errors import InvalidNotificationSettings, PersistenceConflict, UserDisabled
from kvc_persistence.models import NotificationSetting
from kvc_persistence.repositories import (
    NotificationSettingsRepository,
    PersistenceInvariantError,
    UserRepository,
)

MAX_DUE_SOON_DAYS = 30
MAX_TIMEZONE_LENGTH = 128
_FALLBACK_IANA_ZONES = frozenset({"UTC", "Europe/Warsaw", "Europe/Moscow", "Asia/Tokyo"})


class NotificationSettingsService:
    """Read and update KVC-owned notification preferences."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def get_settings(self, user_id: UUID) -> NotificationSettingsResult:
        try:
            async with self._sessionmaker() as session:
                async with session.begin():
                    users = UserRepository(session)
                    notification_settings = NotificationSettingsRepository(session)

                    user = await users.get_by_id(user_id)
                    if user is None:
                        raise PersistenceConflict("KVC user is missing for notification settings")
                    if self._as_user_status(user.status) == "DISABLED":
                        raise UserDisabled("KVC user is disabled")

                    settings = await notification_settings.get_for_user(user_id)
                    if settings is None:
                        raise PersistenceConflict("notification settings are missing")
                    return self._to_result(settings)
        except (IntegrityError, PersistenceInvariantError) as exc:
            raise PersistenceConflict("notification settings persistence conflict") from exc

    async def update_settings(
        self,
        input: UpdateNotificationSettingsInput,
    ) -> NotificationSettingsResult:
        enabled = self._validate_enabled(input.enabled)
        due_soon_days = self._validate_due_soon_days(input.due_soon_days)
        timezone = self._validate_timezone(input.timezone)

        try:
            async with self._sessionmaker() as session:
                async with session.begin():
                    users = UserRepository(session)
                    notification_settings = NotificationSettingsRepository(session)

                    user = await users.get_by_id_for_update(input.user_id)
                    if user is None:
                        raise PersistenceConflict("KVC user is missing for notification settings")
                    if self._as_user_status(user.status) == "DISABLED":
                        raise UserDisabled("KVC user is disabled")

                    settings = await notification_settings.get_for_user_for_update(input.user_id)
                    if settings is None:
                        raise PersistenceConflict("notification settings are missing")
                    settings = await notification_settings.update_settings(
                        settings,
                        enabled=enabled,
                        due_soon_days=due_soon_days,
                        timezone=timezone,
                    )
                    return self._to_result(settings)
        except (IntegrityError, PersistenceInvariantError) as exc:
            raise PersistenceConflict("notification settings persistence conflict") from exc

    def _validate_enabled(self, value: bool) -> bool:
        if not isinstance(value, bool):
            raise InvalidNotificationSettings("enabled must be boolean")
        return value

    def _validate_due_soon_days(self, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidNotificationSettings("due_soon_days must be an integer")
        if value < 0 or value > MAX_DUE_SOON_DAYS:
            raise InvalidNotificationSettings("due_soon_days is out of range")
        return value

    def _validate_timezone(self, value: str) -> str:
        if not isinstance(value, str):
            raise InvalidNotificationSettings("timezone must be a string")
        timezone = value.strip()
        if timezone == "" or len(timezone) > MAX_TIMEZONE_LENGTH:
            raise InvalidNotificationSettings("timezone is invalid")
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            if timezone in _FALLBACK_IANA_ZONES:
                return timezone
            raise InvalidNotificationSettings("timezone is invalid") from exc
        except ValueError as exc:
            raise InvalidNotificationSettings("timezone is invalid") from exc
        return timezone

    def _to_result(self, settings: NotificationSetting) -> NotificationSettingsResult:
        return NotificationSettingsResult(
            user_id=settings.user_id,
            enabled=settings.enabled,
            due_soon_days=settings.due_soon_days,
            timezone=settings.timezone,
        )

    def _as_user_status(self, status: str) -> UserStatus:
        if status == "ACTIVE":
            return "ACTIVE"
        if status == "DISABLED":
            return "DISABLED"
        raise PersistenceConflict("unsupported persisted user status")


__all__ = ["NotificationSettingsService"]
