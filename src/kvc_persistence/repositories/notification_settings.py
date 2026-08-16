"""Notification settings repository primitives."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kvc_persistence.models import NotificationSetting
from kvc_persistence.repositories.contracts import PersistenceInvariantError
from kvc_persistence.repositories.users import UserRepository, _scalar_one_or_none


class NotificationSettingsRepository:
    """Persistence primitives for per-user notification preferences."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, user_id: uuid.UUID) -> NotificationSetting | None:
        return await _scalar_one_or_none(
            self._session,
            select(NotificationSetting).where(NotificationSetting.user_id == user_id),
        )

    async def get_for_user_for_update(self, user_id: uuid.UUID) -> NotificationSetting | None:
        return await _scalar_one_or_none(
            self._session,
            select(NotificationSetting)
            .where(NotificationSetting.user_id == user_id)
            .with_for_update(),
        )

    async def get_or_create_for_user(self, user_id: uuid.UUID) -> NotificationSetting:
        user = await UserRepository(self._session).get_by_id_for_update(user_id)
        if user is None:
            raise PersistenceInvariantError(
                f"Cannot create notification settings for missing user: user_id={user_id}"
            )

        existing = await self.get_for_user(user_id)
        if existing is not None:
            return existing

        settings = NotificationSetting(user_id=user_id)
        self._session.add(settings)
        await self._session.flush()
        await self._session.refresh(settings)
        return settings

    async def update_settings(
        self,
        settings: NotificationSetting,
        *,
        enabled: bool,
        due_soon_days: int,
        timezone: str,
    ) -> NotificationSetting:
        settings.enabled = enabled
        settings.due_soon_days = due_soon_days
        settings.timezone = timezone
        await self._session.flush()
        await self._session.refresh(settings)
        return settings

    async def list_enabled(self) -> list[NotificationSetting]:
        result = await self._session.execute(
            select(NotificationSetting)
            .where(NotificationSetting.enabled.is_(True))
            .order_by(NotificationSetting.user_id)
        )
        return list(result.scalars().all())
