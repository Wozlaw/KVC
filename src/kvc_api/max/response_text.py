"""MAX service-command response text."""

from __future__ import annotations

HELP_TEXT = (
    "Доступные команды:\n"
    "/connect — подключить Kaiten\n"
    "/reconnect — заменить или восстановить подключение\n"
    "/connection — статус подключения\n"
    "/status — то же, что /connection\n"
    "/disable — отключить подключение\n"
    "/help — справка"
)
GROUP_UNSUPPORTED_TEXT = "KVC пока работает только в личном диалоге с ботом."
IDENTITY_CONFLICT_TEXT = "Не удалось безопасно связать этот MAX-диалог. Обратитесь в поддержку."
USER_DISABLED_TEXT = "Учётная запись KVC отключена. Доступны только справочные команды."
TEMPORARY_ERROR_TEXT = "Сервис временно не готов обработать команду. Попробуйте позже."
UNKNOWN_COMMAND_TEXT = "Команда не распознана. Отправьте /help."
NON_COMMAND_TEXT = "Отправьте /help, чтобы посмотреть доступные команды."
NOTIFICATIONS_LATER_TEXT = "Настройки уведомлений появятся на следующем этапе."
START_MISSING_CONNECTION_TEXT = (
    "KVC готов к работе. Kaiten ещё не подключён. Используйте /connect, затем /help."
)
START_CONNECTED_TEXT = "KVC готов к работе. Kaiten подключён. Используйте /connection или /help."
START_NEEDS_REAUTH_TEXT = (
    "KVC готов к работе. Подключение Kaiten требует повторной авторизации. Используйте /reconnect."
)
START_DISABLED_CONNECTION_TEXT = (
    "KVC готов к работе. Подключение Kaiten отключено. Используйте /reconnect."
)
CONNECT_OPEN_TEXT = "Откройте Mini App, чтобы подключить Kaiten."
CONNECT_OPEN_LABEL = "Подключить Kaiten"
CONNECT_ALREADY_ACTIVE_TEXT = "Kaiten уже подключён. Для замены подключения используйте /reconnect."
CONNECT_NEEDS_REAUTH_TEXT = "Подключение требует повторной авторизации. Используйте /reconnect."
CONNECT_DISABLED_TEXT = "Подключение отключено. Для повторного подключения используйте /reconnect."
RECONNECT_OPEN_TEXT = "Откройте Mini App, чтобы переподключить Kaiten."
RECONNECT_OPEN_LABEL = "Переподключить Kaiten"
RECONNECT_MISSING_TEXT = "Kaiten ещё не подключён. Используйте /connect."
CONNECTION_MISSING_TEXT = "Kaiten не подключён. Используйте /connect."
CONNECTION_ACTIVE_TEXT = "Kaiten подключён. Для замены используйте /reconnect."
CONNECTION_NEEDS_REAUTH_TEXT = "Требуется переподключение Kaiten. Используйте /reconnect."
CONNECTION_DISABLED_TEXT = "Подключение Kaiten отключено. Используйте /reconnect."
DISABLE_MISSING_TEXT = "Kaiten не подключён."
DISABLE_SUCCESS_TEXT = "Подключение Kaiten отключено."
MINI_APP_UNAVAILABLE_TEXT = "Mini App временно недоступен. Попробуйте позже."


__all__ = [
    "CONNECT_ALREADY_ACTIVE_TEXT",
    "CONNECT_DISABLED_TEXT",
    "CONNECT_NEEDS_REAUTH_TEXT",
    "CONNECT_OPEN_LABEL",
    "CONNECT_OPEN_TEXT",
    "CONNECTION_ACTIVE_TEXT",
    "CONNECTION_DISABLED_TEXT",
    "CONNECTION_MISSING_TEXT",
    "CONNECTION_NEEDS_REAUTH_TEXT",
    "DISABLE_MISSING_TEXT",
    "DISABLE_SUCCESS_TEXT",
    "GROUP_UNSUPPORTED_TEXT",
    "HELP_TEXT",
    "IDENTITY_CONFLICT_TEXT",
    "MINI_APP_UNAVAILABLE_TEXT",
    "NON_COMMAND_TEXT",
    "NOTIFICATIONS_LATER_TEXT",
    "RECONNECT_MISSING_TEXT",
    "RECONNECT_OPEN_LABEL",
    "RECONNECT_OPEN_TEXT",
    "START_CONNECTED_TEXT",
    "START_DISABLED_CONNECTION_TEXT",
    "START_MISSING_CONNECTION_TEXT",
    "START_NEEDS_REAUTH_TEXT",
    "TEMPORARY_ERROR_TEXT",
    "UNKNOWN_COMMAND_TEXT",
    "USER_DISABLED_TEXT",
]
