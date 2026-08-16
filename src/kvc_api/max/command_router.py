"""Pure deterministic MAX command router."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MaxServiceCommand(StrEnum):
    """Normalized branch-004 service command identifiers."""

    START = "START"
    HELP = "HELP"
    CONNECT = "CONNECT"
    RECONNECT = "RECONNECT"
    CONNECTION = "CONNECTION"
    NOTIFICATIONS = "NOTIFICATIONS"
    DISABLE = "DISABLE"
    UNKNOWN = "UNKNOWN"
    NON_COMMAND = "NON_COMMAND"


@dataclass(frozen=True)
class CommandRoute:
    """Pure routing result for a MAX message text."""

    command: MaxServiceCommand
    raw_command: str | None = None


class CommandRouter:
    """Recognize the frozen branch-004 command set without executing it."""

    _COMMANDS = {
        "start": MaxServiceCommand.START,
        "help": MaxServiceCommand.HELP,
        "connect": MaxServiceCommand.CONNECT,
        "reconnect": MaxServiceCommand.RECONNECT,
        "connection": MaxServiceCommand.CONNECTION,
        "status": MaxServiceCommand.CONNECTION,
        "notifications": MaxServiceCommand.NOTIFICATIONS,
        "disable": MaxServiceCommand.DISABLE,
    }

    def route(self, text: str | None) -> CommandRoute:
        if text is None:
            return CommandRoute(MaxServiceCommand.NON_COMMAND)

        stripped = text.strip()
        if not stripped or not stripped.startswith("/"):
            return CommandRoute(MaxServiceCommand.NON_COMMAND)

        parts = stripped.split()
        command_token = parts[0][1:]
        if len(parts) > 1 or command_token == "":
            return CommandRoute(MaxServiceCommand.UNKNOWN, raw_command=parts[0])

        command_name = command_token.split("@", maxsplit=1)[0].casefold()
        command = self._COMMANDS.get(command_name, MaxServiceCommand.UNKNOWN)
        return CommandRoute(command, raw_command=parts[0])


__all__ = ["CommandRoute", "CommandRouter", "MaxServiceCommand"]
