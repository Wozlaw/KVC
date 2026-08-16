"""MAX update dispatcher tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import uuid4

import pytest

from kvc_api.max import DispatchStatus, MaxServiceCommand, UpdateDispatcher
from kvc_api.max.dispatcher import WebhookRetryableDispatchError
from kvc_api.max.service_commands import ServiceCommandHandler
from kvc_application.dto import IdentityResolution, ResolveMaxIdentityInput
from kvc_application.errors import IdentityConflict, PersistenceConflict
from kvc_integrations.max.context_signing import MiniAppContextSigner
from kvc_integrations.max.dto import MaxIncomingUpdate, MaxSentMessage
from kvc_integrations.max.errors import MaxApiRateLimitError, MaxApiRecipientError


def private_update(*, chat_id: str = "chat-1", text: str | None = "/start") -> MaxIncomingUpdate:
    return MaxIncomingUpdate(
        source="webhook",
        update_type="message_created",
        timestamp=1,
        raw_event_type="message_created",
        chat_id=chat_id,
        chat_type="PRIVATE",
        max_user_id="user-1",
        message_id="mid-1",
        message_text=text,
        message_timestamp=2,
        callback_payload=None,
    )


def non_private_update(chat_type: str) -> MaxIncomingUpdate:
    return MaxIncomingUpdate(
        source="webhook",
        update_type="message_created",
        timestamp=1,
        raw_event_type="message_created",
        chat_id=f"{chat_type.lower()}-1",
        chat_type=chat_type,
        max_user_id="user-1",
        message_id="mid-1",
        message_text="/start",
        message_timestamp=2,
        callback_payload=None,
    )


class FakeIdentityService:
    def __init__(
        self,
        *,
        exc: Exception | None = None,
        user_status: str = "ACTIVE",
        connection_status: str | None = None,
    ) -> None:
        self.calls: list[ResolveMaxIdentityInput] = []
        self.exc = exc
        self.user_status = user_status
        self.connection_status = connection_status

    async def resolve_or_onboard_private_max_user(
        self,
        input: ResolveMaxIdentityInput,
    ) -> IdentityResolution:
        self.calls.append(input)
        if self.exc is not None:
            raise self.exc
        return IdentityResolution(
            user_id=uuid4(),
            max_chat_binding_id=uuid4(),
            user_status="DISABLED" if self.user_status == "DISABLED" else "ACTIVE",
            is_new_user=False,
            kaiten_connection_status=self.connection_status,  # type: ignore[arg-type]
        )


class FakeSender:
    def __init__(self, *, exc: Exception | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.open_app_calls: list[tuple[str, str, str, str]] = []
        self.exc = exc

    async def send_text_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        format: None = None,
        notify: bool = True,
    ) -> MaxSentMessage:
        self.calls.append((chat_id, text))
        if self.exc is not None:
            raise self.exc
        return MaxSentMessage(message_id="mid-out", chat_id=chat_id, timestamp=3)

    async def send_open_app_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        context_ref: str,
        label: str,
        format: None = None,
        notify: bool = True,
    ) -> MaxSentMessage:
        self.open_app_calls.append((chat_id, text, context_ref, label))
        if self.exc is not None:
            raise self.exc
        return MaxSentMessage(message_id="mid-out", chat_id=chat_id, timestamp=3)


def dispatcher(
    identity: FakeIdentityService,
    sender: FakeSender,
) -> UpdateDispatcher:
    return UpdateDispatcher(
        identity_service=identity,
        message_sender=sender,
        allowed_update_types=("message_created", "message_callback", "bot_started"),
    )


def dispatcher_with_factory(
    identity_factory: Callable[[], FakeIdentityService],
    sender: FakeSender,
) -> UpdateDispatcher:
    return UpdateDispatcher(
        identity_resolver_factory=identity_factory,
        message_sender=sender,
        allowed_update_types=("message_created", "message_callback", "bot_started"),
    )


def dispatcher_with_handler(
    identity: FakeIdentityService,
    sender: FakeSender,
    handler: ServiceCommandHandler,
) -> UpdateDispatcher:
    return UpdateDispatcher(
        identity_service=identity,
        message_sender=sender,
        service_command_handler=handler,
        allowed_update_types=("message_created", "message_callback", "bot_started"),
    )


@pytest.mark.asyncio
async def test_dispatcher_resolves_private_identity_and_replies_through_sender() -> None:
    identity = FakeIdentityService()
    sender = FakeSender()

    outcome = await dispatcher(identity, sender).dispatch(private_update(text="/help"))

    assert outcome.status is DispatchStatus.RESPONDED
    assert outcome.command is MaxServiceCommand.HELP
    assert outcome.identity_resolved is True
    assert sender.calls[0][0] == "chat-1"
    assert "/help" in sender.calls[0][1]
    assert identity.calls == [
        ResolveMaxIdentityInput(
            max_user_id="user-1",
            max_chat_id="chat-1",
            chat_type="PRIVATE",
        )
    ]


@pytest.mark.asyncio
async def test_dispatcher_uses_identity_factory_per_private_dispatch() -> None:
    identities = [FakeIdentityService(), FakeIdentityService()]
    factory_calls = 0

    def identity_factory() -> FakeIdentityService:
        nonlocal factory_calls
        identity = identities[factory_calls]
        factory_calls += 1
        return identity

    sender = FakeSender()
    tested_dispatcher = dispatcher_with_factory(identity_factory, sender)

    await tested_dispatcher.dispatch(private_update(chat_id="chat-a"))
    await tested_dispatcher.dispatch(private_update(chat_id="chat-b"))

    assert factory_calls == 2
    assert len(identities[0].calls) == 1
    assert len(identities[1].calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("chat_type", ["GROUP", "CHANNEL", "UNKNOWN"])
async def test_dispatcher_does_not_resolve_identity_for_group_channel_or_unknown(
    chat_type: str,
) -> None:
    identity = FakeIdentityService()
    sender = FakeSender()
    update = non_private_update(chat_type)

    outcome = await dispatcher(identity, sender).dispatch(update)

    assert outcome.status is DispatchStatus.RESPONDED
    assert identity.calls == []
    assert sender.calls[0][0] == f"{chat_type.lower()}-1"


@pytest.mark.asyncio
async def test_dispatcher_ignores_unsupported_update_type() -> None:
    identity = FakeIdentityService()
    sender = FakeSender()
    update = private_update()
    update = MaxIncomingUpdate(
        **{
            **update.__dict__,
            "update_type": "message_removed",
            "raw_event_type": "message_removed",
        }
    )

    outcome = await dispatcher(identity, sender).dispatch(update)

    assert outcome.status is DispatchStatus.IGNORED
    assert identity.calls == []
    assert sender.calls == []


@pytest.mark.asyncio
async def test_dispatcher_maps_bot_started_to_start_command() -> None:
    identity = FakeIdentityService()
    sender = FakeSender()
    update = MaxIncomingUpdate(
        source="webhook",
        update_type="bot_started",
        timestamp=1,
        raw_event_type="bot_started",
        chat_id="chat-1",
        chat_type="PRIVATE",
        max_user_id="user-1",
        message_id=None,
        message_text=None,
        message_timestamp=None,
        callback_payload=None,
    )

    outcome = await dispatcher(identity, sender).dispatch(update)

    assert outcome.command is MaxServiceCommand.START
    assert outcome.status is DispatchStatus.RESPONDED


@pytest.mark.asyncio
async def test_dispatcher_ignores_callback_without_whitelisted_stage_action() -> None:
    identity = FakeIdentityService()
    sender = FakeSender()
    update = MaxIncomingUpdate(
        source="webhook",
        update_type="message_callback",
        timestamp=1,
        raw_event_type="message_callback",
        chat_id="chat-1",
        chat_type="PRIVATE",
        max_user_id="user-1",
        message_id="mid-1",
        message_text=None,
        message_timestamp=2,
        callback_payload="untrusted",
    )

    outcome = await dispatcher(identity, sender).dispatch(update)

    assert outcome.status is DispatchStatus.IGNORED
    assert outcome.identity_resolved is True
    assert sender.calls == []


@pytest.mark.asyncio
async def test_dispatcher_identity_conflict_maps_to_safe_reply() -> None:
    identity = FakeIdentityService(exc=IdentityConflict("raw ids must not leak"))
    sender = FakeSender()

    outcome = await dispatcher(identity, sender).dispatch(private_update())

    assert outcome.status is DispatchStatus.RESPONDED
    assert "raw ids" not in sender.calls[0][1]


@pytest.mark.asyncio
async def test_dispatcher_disabled_user_gets_disabled_policy_reply() -> None:
    identity = FakeIdentityService(user_status="DISABLED")
    sender = FakeSender()

    outcome = await dispatcher(identity, sender).dispatch(private_update(text="/connect"))

    assert outcome.status is DispatchStatus.RESPONDED
    assert outcome.command is MaxServiceCommand.CONNECT
    assert "отключена" in sender.calls[0][1]


@pytest.mark.asyncio
async def test_dispatcher_connect_uses_open_app_sender_path() -> None:
    identity = FakeIdentityService()
    sender = FakeSender()
    tested_dispatcher = dispatcher_with_handler(
        identity,
        sender,
        ServiceCommandHandler(
            context_signer=MiniAppContextSigner("synthetic-context-secret"),
            mini_app_launch_enabled=True,
            now=lambda: 1_700_000_000,
        ),
    )

    outcome = await tested_dispatcher.dispatch(private_update(text="/connect"))

    assert outcome.status is DispatchStatus.RESPONDED
    assert outcome.command is MaxServiceCommand.CONNECT
    assert sender.calls == []
    assert len(sender.open_app_calls) == 1
    chat_id, text, context_ref, label = sender.open_app_calls[0]
    assert chat_id == "chat-1"
    assert text == "Откройте Mini App, чтобы подключить Kaiten."
    assert label == "Подключить Kaiten"
    assert "." not in context_ref


@pytest.mark.asyncio
async def test_dispatcher_status_alias_uses_connection_command_text() -> None:
    identity = FakeIdentityService(connection_status="ACTIVE")
    sender = FakeSender()

    outcome = await dispatcher(identity, sender).dispatch(private_update(text="/status"))

    assert outcome.command is MaxServiceCommand.CONNECTION
    assert sender.calls == [("chat-1", "Kaiten подключён. Для замены используйте /reconnect.")]


@pytest.mark.asyncio
async def test_dispatcher_retryable_outbound_error_propagates_without_retry() -> None:
    identity = FakeIdentityService()
    sender = FakeSender(exc=MaxApiRateLimitError("rate", status_code=429))

    with pytest.raises(WebhookRetryableDispatchError):
        await dispatcher(identity, sender).dispatch(private_update())

    assert len(sender.calls) == 1


@pytest.mark.asyncio
async def test_dispatcher_non_retryable_outbound_error_is_terminal_without_retry() -> None:
    identity = FakeIdentityService()
    sender = FakeSender(exc=MaxApiRecipientError("recipient", status_code=404))

    outcome = await dispatcher(identity, sender).dispatch(private_update())

    assert outcome.status is DispatchStatus.OUTBOUND_NON_RETRYABLE_FAILURE
    assert len(sender.calls) == 1


@pytest.mark.asyncio
async def test_dispatcher_persistence_conflict_is_retryable_webhook_failure() -> None:
    identity = FakeIdentityService(exc=PersistenceConflict("db"))
    sender = FakeSender()

    with pytest.raises(WebhookRetryableDispatchError):
        await dispatcher(identity, sender).dispatch(private_update())

    assert sender.calls == []


@pytest.mark.asyncio
async def test_dispatcher_serializes_same_chat() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingIdentity(FakeIdentityService):
        def __init__(self) -> None:
            super().__init__()
            self.active = 0
            self.max_active = 0

        async def resolve_or_onboard_private_max_user(
            self,
            input: ResolveMaxIdentityInput,
        ) -> IdentityResolution:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            entered.set()
            await release.wait()
            self.active -= 1
            return await super().resolve_or_onboard_private_max_user(input)

    identity = BlockingIdentity()
    sender = FakeSender()
    tested_dispatcher = dispatcher(identity, sender)
    first = asyncio.create_task(tested_dispatcher.dispatch(private_update(chat_id="same")))
    second = asyncio.create_task(tested_dispatcher.dispatch(private_update(chat_id="same")))

    await asyncio.wait_for(entered.wait(), timeout=1)
    release.set()
    await asyncio.gather(first, second)

    assert identity.max_active == 1


@pytest.mark.asyncio
async def test_dispatcher_allows_different_chat_concurrency() -> None:
    both_entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingIdentity(FakeIdentityService):
        def __init__(self) -> None:
            super().__init__()
            self.active = 0

        async def resolve_or_onboard_private_max_user(
            self,
            input: ResolveMaxIdentityInput,
        ) -> IdentityResolution:
            self.active += 1
            if self.active == 2:
                both_entered.set()
            await release.wait()
            self.active -= 1
            return await super().resolve_or_onboard_private_max_user(input)

    identity = BlockingIdentity()
    sender = FakeSender()
    tested_dispatcher = dispatcher(identity, sender)
    first = asyncio.create_task(tested_dispatcher.dispatch(private_update(chat_id="chat-a")))
    second = asyncio.create_task(tested_dispatcher.dispatch(private_update(chat_id="chat-b")))

    await asyncio.wait_for(both_entered.wait(), timeout=1)
    release.set()
    await asyncio.gather(first, second)
