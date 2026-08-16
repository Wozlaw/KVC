"""SQLAlchemy ORM models for the MVP KVC-owned service schema."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from kvc_persistence.base import Base

ACTIVE_PENDING_STATES = (
    "RECEIVED",
    "PARSED",
    "RESOLVING",
    "NEEDS_CLARIFICATION",
    "READY",
)

PENDING_STATES = (*ACTIVE_PENDING_STATES, "EXECUTED", "FAILED", "CANCELLED", "EXPIRED")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    """Internal KVC user identity."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVE'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        onupdate=_utcnow,
        server_default=text("now()"),
    )


class MaxChat(Base):
    """MAX private chat binding for a KVC user."""

    __tablename__ = "max_chats"
    __table_args__ = (
        CheckConstraint("chat_type IN ('PRIVATE')", name="chat_type"),
        UniqueConstraint("max_chat_id", name="uq_max_chats_max_chat_id"),
        Index(
            "uq_max_chats_max_user_id_private",
            "max_user_id",
            unique=True,
            postgresql_where=text("chat_type = 'PRIVATE'"),
        ),
        Index(
            "uq_max_chats_user_primary",
            "user_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    max_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    max_chat_id: Mapped[str] = mapped_column(Text, nullable=False)
    chat_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PRIVATE'"))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        onupdate=_utcnow,
        server_default=text("now()"),
    )


class KaitenConnection(Base):
    """Per-user encrypted Kaiten API connection settings."""

    __tablename__ = "kaiten_connections"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'DISABLED', 'NEEDS_REAUTH')", name="status"),
        CheckConstraint("token_encryption_version > 0", name="token_encryption_version_positive"),
        UniqueConstraint("user_id", name="uq_kaiten_connections_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    api_base_url: Mapped[str] = mapped_column(Text, nullable=False)
    kaiten_user_id: Mapped[str | None] = mapped_column(Text)
    workspace_id: Mapped[str | None] = mapped_column(Text)
    encrypted_api_token: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    token_encryption_version: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("1"),
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVE'"))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        onupdate=_utcnow,
        server_default=text("now()"),
    )


class DialogSession(Base):
    """Bounded restart-safe dialog context."""

    __tablename__ = "dialog_sessions"
    __table_args__ = (
        Index(
            "uq_dialog_sessions_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index("ix_dialog_sessions_max_chat_binding_id", "max_chat_binding_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    max_chat_binding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("max_chats.id", ondelete="SET NULL"),
    )
    current_board_id: Mapped[str | None] = mapped_column(Text)
    current_board_name: Mapped[str | None] = mapped_column(Text)
    current_card_id: Mapped[str | None] = mapped_column(Text)
    current_card_title: Mapped[str | None] = mapped_column(Text)
    previous_user_message: Mapped[str | None] = mapped_column(Text)
    previous_bot_message: Mapped[str | None] = mapped_column(Text)
    last_card_list: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    last_card_list_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        onupdate=_utcnow,
        server_default=text("now()"),
    )


class PendingCommand(Base):
    """Durable transient command workflow state."""

    __tablename__ = "pending_commands"
    __table_args__ = (
        CheckConstraint(
            "state IN ("
            "'RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY', "
            "'EXECUTED', 'FAILED', 'CANCELLED', 'EXPIRED'"
            ")",
            name="state",
        ),
        CheckConstraint("clarification_attempts >= 0", name="clarification_attempts_non_negative"),
        Index(
            "uq_pending_commands_one_active_per_session",
            "dialog_session_id",
            unique=True,
            postgresql_where=text(
                "state IN ('RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY')"
            ),
        ),
        Index("ix_pending_commands_user_state", "user_id", "state"),
        Index(
            "ix_pending_commands_expires_at_active",
            "expires_at",
            postgresql_where=text(
                "state IN ('RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY') "
                "AND expires_at IS NOT NULL"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dialog_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dialog_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    original_message: Mapped[str] = mapped_column(Text, nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("jsonb_build_object('version', 1, 'payload', jsonb_build_object())"),
    )
    unresolved_entity: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    candidates: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'RECEIVED'"))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    clarification_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        onupdate=_utcnow,
        server_default=text("now()"),
    )


class NotificationSetting(Base):
    """Per-user notification preferences."""

    __tablename__ = "notification_settings"
    __table_args__ = (
        CheckConstraint("due_soon_days BETWEEN 0 AND 30", name="due_soon_days_range"),
        Index("ix_notification_settings_enabled_user", "enabled", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    due_soon_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'UTC'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        onupdate=_utcnow,
        server_default=text("now()"),
    )


class NotificationHistory(Base):
    """Notification reservation, deduplication, and delivery audit."""

    __tablename__ = "notification_history"
    __table_args__ = (
        CheckConstraint(
            "notification_type IN ('DUE_SOON', 'DUE_TODAY', 'OVERDUE')",
            name="type",
        ),
        CheckConstraint(
            "delivery_status IN ('RESERVED', 'SENT', 'FAILED')",
            name="delivery_status",
        ),
        UniqueConstraint(
            "user_id",
            "kaiten_card_id",
            "due_at",
            "due_date_time_present",
            "notification_type",
            name="uq_notification_history_dedup",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kaiten_card_id: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date_time_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notification_type: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'RESERVED'"),
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_type: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        onupdate=_utcnow,
        server_default=text("now()"),
    )
