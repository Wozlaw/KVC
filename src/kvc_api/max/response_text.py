"""Short provisional MAX transport responses for stage 004-03."""

from __future__ import annotations

from kvc_api.max.command_router import MaxServiceCommand

HELP_TEXT = "KVC понимает команды /start, /help, /connect, /connection, /notifications, /disable."
GROUP_UNSUPPORTED_TEXT = "KVC пока работает только в личном диалоге с ботом."
IDENTITY_CONFLICT_TEXT = "Не удалось безопасно связать этот MAX-диалог. Обратитесь в поддержку."
USER_DISABLED_TEXT = "Учётная запись KVC отключена. Доступны только справочные команды."
TEMPORARY_ERROR_TEXT = "Сервис временно не готов обработать команду. Попробуйте позже."
UNKNOWN_COMMAND_TEXT = "Команда не распознана. Отправьте /help."
NON_COMMAND_TEXT = "Отправьте /help, чтобы посмотреть доступные команды."
RECOGNIZED_LATER_TEXT = "Команда распознана. Полный сценарий будет подключён на следующем этапе."


def provisional_command_response(command: MaxServiceCommand, *, disabled: bool = False) -> str:
    """Return stable non-secret text for the narrow 004-03 command boundary."""

    if disabled:
        return USER_DISABLED_TEXT
    if command in {MaxServiceCommand.START, MaxServiceCommand.HELP}:
        return HELP_TEXT
    if command in {
        MaxServiceCommand.CONNECT,
        MaxServiceCommand.RECONNECT,
        MaxServiceCommand.CONNECTION,
        MaxServiceCommand.NOTIFICATIONS,
        MaxServiceCommand.DISABLE,
    }:
        return RECOGNIZED_LATER_TEXT
    if command is MaxServiceCommand.NON_COMMAND:
        return NON_COMMAND_TEXT
    return UNKNOWN_COMMAND_TEXT


__all__ = [
    "GROUP_UNSUPPORTED_TEXT",
    "HELP_TEXT",
    "IDENTITY_CONFLICT_TEXT",
    "NON_COMMAND_TEXT",
    "RECOGNIZED_LATER_TEXT",
    "TEMPORARY_ERROR_TEXT",
    "UNKNOWN_COMMAND_TEXT",
    "USER_DISABLED_TEXT",
    "provisional_command_response",
]
