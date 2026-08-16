"""MAX command router tests."""

from kvc_api.max.command_router import CommandRouter, MaxServiceCommand


def test_command_router_recognizes_frozen_command_set() -> None:
    router = CommandRouter()

    assert router.route("/start").command is MaxServiceCommand.START
    assert router.route("/help").command is MaxServiceCommand.HELP
    assert router.route("/connect").command is MaxServiceCommand.CONNECT
    assert router.route("/reconnect").command is MaxServiceCommand.RECONNECT
    assert router.route("/connection").command is MaxServiceCommand.CONNECTION
    assert router.route("/notifications").command is MaxServiceCommand.NOTIFICATIONS
    assert router.route("/disable").command is MaxServiceCommand.DISABLE


def test_command_router_normalizes_whitespace_case_and_bot_suffix() -> None:
    router = CommandRouter()

    assert router.route("  /START@TestBot  ").command is MaxServiceCommand.START


def test_command_router_aliases_status_to_connection() -> None:
    router = CommandRouter()

    assert router.route("/status").command is MaxServiceCommand.CONNECTION


def test_command_router_rejects_unexpected_arguments() -> None:
    router = CommandRouter()

    assert router.route("/start extra").command is MaxServiceCommand.UNKNOWN


def test_command_router_distinguishes_unknown_and_non_command_text() -> None:
    router = CommandRouter()

    assert router.route("/cards").command is MaxServiceCommand.UNKNOWN
    assert router.route("hello").command is MaxServiceCommand.NON_COMMAND
    assert router.route(None).command is MaxServiceCommand.NON_COMMAND
