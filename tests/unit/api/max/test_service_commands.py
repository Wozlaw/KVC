"""MAX service-command handler tests."""

from __future__ import annotations

import re
from uuid import UUID, uuid4

import pytest

from kvc_api.max.command_router import MaxServiceCommand
from kvc_api.max.response_text import (
    CONNECT_ALREADY_ACTIVE_TEXT,
    CONNECTION_ACTIVE_TEXT,
    CONNECTION_MISSING_TEXT,
    DISABLE_MISSING_TEXT,
    DISABLE_SUCCESS_TEXT,
    HELP_TEXT,
    NOTIFICATIONS_LATER_TEXT,
    RECONNECT_MISSING_TEXT,
    USER_DISABLED_TEXT,
)
from kvc_api.max.service_commands import (
    CONNECT_CONTEXT_TTL_SECONDS,
    ServiceCommandContext,
    ServiceCommandHandler,
)
from kvc_application.dto import IdentityResolution, KaitenConnectionResult
from kvc_application.errors import KaitenConnectionMissing
from kvc_integrations.max.context_signing import MiniAppContextPurpose, MiniAppContextSigner

SECRET = "synthetic-context-secret"
NOW = 1_700_000_000
MAX_USER_ID = "max-user-a"
MAX_CHAT_ID = "max-chat-a"
MAX_STARTAPP_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class FakeDisabler:
    def __init__(self, *, exc: Exception | None = None) -> None:
        self.calls: list[UUID] = []
        self.exc = exc

    async def disable_connection(self, user_id: UUID) -> KaitenConnectionResult:
        self.calls.append(user_id)
        if self.exc is not None:
            raise self.exc
        return KaitenConnectionResult(
            connection_id=uuid4(),
            user_id=user_id,
            status="DISABLED",
            api_base_url="https://synthetic.kaiten.example/api/latest",
            kaiten_user_id=None,
            workspace_id=None,
            last_verified_at=None,
        )


def identity(
    *,
    user_status: str = "ACTIVE",
    connection_status: str | None = None,
) -> IdentityResolution:
    return IdentityResolution(
        user_id=UUID("00000000-0000-0000-0000-000000000401"),
        max_chat_binding_id=UUID("00000000-0000-0000-0000-000000000402"),
        user_status="DISABLED" if user_status == "DISABLED" else "ACTIVE",
        is_new_user=False,
        kaiten_connection_status=connection_status,  # type: ignore[arg-type]
    )


def context(command: MaxServiceCommand, resolution: IdentityResolution) -> ServiceCommandContext:
    return ServiceCommandContext(
        command=command,
        identity=resolution,
        max_user_id=MAX_USER_ID,
        max_chat_id=MAX_CHAT_ID,
    )


def handler(
    *,
    disabler: FakeDisabler | None = None,
    launch_enabled: bool = True,
) -> ServiceCommandHandler:
    return ServiceCommandHandler(
        context_signer=MiniAppContextSigner(SECRET),
        kaiten_connection_service_factory=None if disabler is None else lambda: disabler,
        mini_app_launch_enabled=launch_enabled,
        now=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_start_missing_and_active_connection_copy() -> None:
    missing = await handler().handle(context(MaxServiceCommand.START, identity()))
    active = await handler().handle(
        context(MaxServiceCommand.START, identity(connection_status="ACTIVE"))
    )

    assert missing.kind == "text"
    assert "/connect" in missing.text
    assert active.kind == "text"
    assert "Kaiten подключён" in active.text


@pytest.mark.asyncio
async def test_help_lists_only_current_commands() -> None:
    action = await handler().handle(context(MaxServiceCommand.HELP, identity()))

    assert action.text == HELP_TEXT
    assert "/notifications" not in action.text
    assert "/cards" not in action.text
    assert len(action.text) < 4000


@pytest.mark.asyncio
async def test_connect_missing_connection_issues_max_safe_context() -> None:
    action = await handler().handle(context(MaxServiceCommand.CONNECT, identity()))
    signer = MiniAppContextSigner(SECRET)
    binding = signer.make_identity_binding(max_user_id=MAX_USER_ID, chat_id=MAX_CHAT_ID)

    assert action.kind == "open_app"
    assert action.label == "Подключить Kaiten"
    assert action.context_ref is not None
    assert MAX_STARTAPP_RE.fullmatch(action.context_ref)
    assert "." not in action.context_ref
    assert len(action.context_ref) <= 512
    claims = signer.verify(
        action.context_ref,
        expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        expected_identity_binding=binding,
        now=NOW,
    )
    assert claims.expires_at - claims.issued_at == CONNECT_CONTEXT_TTL_SECONDS


@pytest.mark.parametrize("status", ["ACTIVE", "NEEDS_REAUTH", "DISABLED"])
@pytest.mark.asyncio
async def test_connect_existing_connection_does_not_launch(status: str) -> None:
    action = await handler().handle(
        context(MaxServiceCommand.CONNECT, identity(connection_status=status))
    )

    assert action.kind == "text"
    assert action.context_ref is None
    assert action.text != ""
    if status == "ACTIVE":
        assert action.text == CONNECT_ALREADY_ACTIVE_TEXT


@pytest.mark.parametrize("status", ["ACTIVE", "NEEDS_REAUTH", "DISABLED"])
@pytest.mark.asyncio
async def test_reconnect_existing_connection_issues_reconnect_context(status: str) -> None:
    action = await handler().handle(
        context(MaxServiceCommand.RECONNECT, identity(connection_status=status))
    )
    signer = MiniAppContextSigner(SECRET)
    binding = signer.make_identity_binding(max_user_id=MAX_USER_ID, chat_id=MAX_CHAT_ID)

    assert action.kind == "open_app"
    assert action.context_ref is not None
    signer.verify(
        action.context_ref,
        expected_purpose=MiniAppContextPurpose.RECONNECT_KAITEN,
        expected_identity_binding=binding,
        now=NOW,
    )


@pytest.mark.asyncio
async def test_reconnect_missing_points_to_connect() -> None:
    action = await handler().handle(context(MaxServiceCommand.RECONNECT, identity()))

    assert action.kind == "text"
    assert action.text == RECONNECT_MISSING_TEXT


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (None, CONNECTION_MISSING_TEXT),
        ("ACTIVE", CONNECTION_ACTIVE_TEXT),
        ("NEEDS_REAUTH", "Требуется переподключение Kaiten. Используйте /reconnect."),
        ("DISABLED", "Подключение Kaiten отключено. Используйте /reconnect."),
    ],
)
@pytest.mark.asyncio
async def test_connection_status_matrix(status: str | None, expected: str) -> None:
    action = await handler().handle(
        context(MaxServiceCommand.CONNECTION, identity(connection_status=status))
    )

    assert action.kind == "text"
    assert action.text == expected


@pytest.mark.asyncio
async def test_status_alias_uses_connection_command_route() -> None:
    action = await handler().handle(
        context(MaxServiceCommand.CONNECTION, identity(connection_status="ACTIVE"))
    )

    assert action.text == CONNECTION_ACTIVE_TEXT


@pytest.mark.asyncio
async def test_disable_missing_connection_avoids_service_call() -> None:
    disabler = FakeDisabler()
    action = await handler(disabler=disabler).handle(context(MaxServiceCommand.DISABLE, identity()))

    assert action.text == DISABLE_MISSING_TEXT
    assert disabler.calls == []


@pytest.mark.parametrize("status", ["ACTIVE", "NEEDS_REAUTH", "DISABLED"])
@pytest.mark.asyncio
async def test_disable_existing_connection_calls_service_once(status: str) -> None:
    disabler = FakeDisabler()
    action = await handler(disabler=disabler).handle(
        context(MaxServiceCommand.DISABLE, identity(connection_status=status))
    )

    assert action.text == DISABLE_SUCCESS_TEXT
    assert disabler.calls == [identity().user_id]


@pytest.mark.asyncio
async def test_disable_service_missing_connection_maps_to_safe_text() -> None:
    disabler = FakeDisabler(exc=KaitenConnectionMissing("missing"))
    action = await handler(disabler=disabler).handle(
        context(MaxServiceCommand.DISABLE, identity(connection_status="ACTIVE"))
    )

    assert action.text == DISABLE_MISSING_TEXT


@pytest.mark.parametrize("command", [MaxServiceCommand.CONNECT, MaxServiceCommand.RECONNECT])
@pytest.mark.asyncio
async def test_disabled_kvc_user_blocks_connect_and_reconnect(command: MaxServiceCommand) -> None:
    action = await handler().handle(context(command, identity(user_status="DISABLED")))

    assert action.kind == "text"
    assert action.text == USER_DISABLED_TEXT


@pytest.mark.parametrize(
    "command",
    [
        MaxServiceCommand.START,
        MaxServiceCommand.HELP,
        MaxServiceCommand.CONNECTION,
        MaxServiceCommand.DISABLE,
        MaxServiceCommand.NOTIFICATIONS,
    ],
)
@pytest.mark.asyncio
async def test_disabled_kvc_user_matrix_for_non_launch_commands(command: MaxServiceCommand) -> None:
    action = await handler().handle(
        context(command, identity(user_status="DISABLED", connection_status="ACTIVE"))
    )

    assert action.kind == "text"
    assert action.context_ref is None


@pytest.mark.asyncio
async def test_notifications_remains_provisional() -> None:
    action = await handler().handle(context(MaxServiceCommand.NOTIFICATIONS, identity()))

    assert action.text == NOTIFICATIONS_LATER_TEXT


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (MaxServiceCommand.UNKNOWN, "Команда не распознана. Отправьте /help."),
        (MaxServiceCommand.NON_COMMAND, "Отправьте /help, чтобы посмотреть доступные команды."),
    ],
)
@pytest.mark.asyncio
async def test_unknown_and_non_command_regression(
    command: MaxServiceCommand,
    expected: str,
) -> None:
    action = await handler().handle(context(command, identity()))

    assert action.text == expected
