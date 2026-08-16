"""Minimal async repository/query contracts for the MVP persistence model."""

from kvc_persistence.repositories.contracts import PersistenceInvariantError
from kvc_persistence.repositories.dialog_sessions import DialogSessionRepository
from kvc_persistence.repositories.kaiten_connections import KaitenConnectionRepository
from kvc_persistence.repositories.max_chats import MaxChatRepository
from kvc_persistence.repositories.notification_history import NotificationHistoryRepository
from kvc_persistence.repositories.notification_settings import NotificationSettingsRepository
from kvc_persistence.repositories.pending_commands import PendingCommandRepository
from kvc_persistence.repositories.users import UserRepository

__all__ = [
    "DialogSessionRepository",
    "KaitenConnectionRepository",
    "MaxChatRepository",
    "NotificationHistoryRepository",
    "NotificationSettingsRepository",
    "PendingCommandRepository",
    "PersistenceInvariantError",
    "UserRepository",
]
