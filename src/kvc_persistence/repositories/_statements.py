"""Shared SQLAlchemy statement helpers for repository tests and implementations."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.dml import ReturningInsert

from kvc_persistence.models import (
    ACTIVE_PENDING_STATES,
    DialogSession,
    NotificationHistory,
    PendingCommand,
    User,
)


def select_user_for_update(user_id: uuid.UUID) -> Select[tuple[User]]:
    """Build the parent-user row lock used by concurrency-sensitive repositories."""

    return select(User).where(User.id == user_id).with_for_update()


def select_active_dialog_for_update(user_id: uuid.UUID) -> Select[tuple[DialogSession]]:
    """Build the active dialog lock query."""

    return (
        select(DialogSession)
        .where(DialogSession.user_id == user_id, DialogSession.ended_at.is_(None))
        .with_for_update()
    )


def select_dialog_session_for_update(dialog_session_id: uuid.UUID) -> Select[tuple[DialogSession]]:
    """Build the dialog row lock used before pending command creation."""

    return select(DialogSession).where(DialogSession.id == dialog_session_id).with_for_update()


def select_active_pending_command_for_update(
    dialog_session_id: uuid.UUID,
) -> Select[tuple[PendingCommand]]:
    """Build the clarification-safe active pending command lock query."""

    return (
        select(PendingCommand)
        .where(
            PendingCommand.dialog_session_id == dialog_session_id,
            PendingCommand.state.in_(ACTIVE_PENDING_STATES),
        )
        .with_for_update()
    )


def insert_notification_reservation(
    *,
    user_id: uuid.UUID,
    kaiten_card_id: str,
    due_at: datetime,
    due_date_time_present: bool,
    notification_type: str,
) -> ReturningInsert[tuple[NotificationHistory]]:
    """Build the PostgreSQL atomic notification reservation statement."""

    return (
        insert(NotificationHistory)
        .values(
            user_id=user_id,
            kaiten_card_id=kaiten_card_id,
            due_at=due_at,
            due_date_time_present=due_date_time_present,
            notification_type=notification_type,
        )
        .on_conflict_do_nothing(constraint="uq_notification_history_dedup")
        .returning(NotificationHistory)
    )
