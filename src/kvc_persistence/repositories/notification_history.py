"""Notification history repository primitives."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kvc_persistence.models import NotificationHistory
from kvc_persistence.repositories._statements import insert_notification_reservation
from kvc_persistence.repositories.users import _scalar_one_or_none


class NotificationHistoryRepository:
    """Persistence primitives for notification reservation and delivery audit."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reserve(
        self,
        *,
        user_id: uuid.UUID,
        kaiten_card_id: str,
        due_at: datetime,
        due_date_time_present: bool,
        notification_type: str,
    ) -> NotificationHistory | None:
        result = await self._session.execute(
            insert_notification_reservation(
                user_id=user_id,
                kaiten_card_id=kaiten_card_id,
                due_at=due_at,
                due_date_time_present=due_date_time_present,
                notification_type=notification_type,
            )
        )
        reservation = result.scalar_one_or_none()
        if reservation is not None:
            await self._session.flush()
        return reservation

    async def get_by_dedup_key(
        self,
        *,
        user_id: uuid.UUID,
        kaiten_card_id: str,
        due_at: datetime,
        due_date_time_present: bool,
        notification_type: str,
    ) -> NotificationHistory | None:
        return await _scalar_one_or_none(
            self._session,
            select(NotificationHistory).where(
                NotificationHistory.user_id == user_id,
                NotificationHistory.kaiten_card_id == kaiten_card_id,
                NotificationHistory.due_at == due_at,
                NotificationHistory.due_date_time_present == due_date_time_present,
                NotificationHistory.notification_type == notification_type,
            ),
        )

    async def get_by_id_for_update(
        self,
        *,
        user_id: uuid.UUID,
        notification_history_id: uuid.UUID,
    ) -> NotificationHistory | None:
        return await _scalar_one_or_none(
            self._session,
            select(NotificationHistory)
            .where(
                NotificationHistory.user_id == user_id,
                NotificationHistory.id == notification_history_id,
            )
            .with_for_update(),
        )

    async def mark_sent(
        self,
        notification: NotificationHistory,
        *,
        sent_at: datetime,
    ) -> NotificationHistory:
        notification.delivery_status = "SENT"
        notification.sent_at = sent_at
        notification.failed_at = None
        notification.error_type = None
        await self._session.flush()
        await self._session.refresh(notification)
        return notification

    async def mark_failed(
        self,
        notification: NotificationHistory,
        *,
        failed_at: datetime,
        error_type: str,
    ) -> NotificationHistory:
        notification.delivery_status = "FAILED"
        notification.failed_at = failed_at
        notification.error_type = error_type
        await self._session.flush()
        await self._session.refresh(notification)
        return notification
