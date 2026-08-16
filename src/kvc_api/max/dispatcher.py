"""MAX update dispatcher foundation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from kvc_api.max.command_router import CommandRouter, MaxServiceCommand
from kvc_api.max.response_text import (
    GROUP_UNSUPPORTED_TEXT,
    IDENTITY_CONFLICT_TEXT,
)
from kvc_api.max.service_commands import (
    ServiceCommandAction,
    ServiceCommandContext,
    ServiceCommandHandler,
)
from kvc_application.dto import IdentityResolution, ResolveMaxIdentityInput
from kvc_application.errors import IdentityConflict, PersistenceConflict, UserDisabled
from kvc_integrations.max.dto import MaxIncomingUpdate, MaxSentMessage
from kvc_integrations.max.errors import MaxApiError


class DispatchStatus(StrEnum):
    """Sanitized dispatch status categories."""

    IGNORED = "ignored"
    RESPONDED = "responded"
    OUTBOUND_NON_RETRYABLE_FAILURE = "outbound_non_retryable_failure"


@dataclass(frozen=True)
class DispatchOutcome:
    """Safe dispatch result for route/integration tests and callers."""

    status: DispatchStatus
    update_type: str
    command: MaxServiceCommand | None = None
    identity_resolved: bool = False
    response_sent: bool = False


class WebhookRetryableDispatchError(RuntimeError):
    """Raised when MAX webhook delivery may be retried safely."""


class IdentityResolver(Protocol):
    async def resolve_or_onboard_private_max_user(
        self,
        input: ResolveMaxIdentityInput,
    ) -> IdentityResolution: ...


IdentityResolverFactory = Callable[[], IdentityResolver]


class MessageSender(Protocol):
    async def send_text_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        format: None = None,
        notify: bool = True,
    ) -> MaxSentMessage: ...

    async def send_open_app_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        context_ref: str,
        label: str,
        app_path: str | None = None,
        format: None = None,
        notify: bool = True,
    ) -> MaxSentMessage: ...


class UpdateDispatcher:
    """Dispatch normalized MAX updates through identity and command boundaries."""

    def __init__(
        self,
        *,
        identity_service: IdentityResolver | None = None,
        identity_resolver_factory: IdentityResolverFactory | None = None,
        message_sender: MessageSender,
        command_router: CommandRouter | None = None,
        service_command_handler: ServiceCommandHandler | None = None,
        allowed_update_types: tuple[str, ...],
    ) -> None:
        if (identity_service is None) == (identity_resolver_factory is None):
            raise ValueError("Exactly one identity resolver source is required")
        if identity_resolver_factory is not None:
            self._identity_resolver_factory = identity_resolver_factory
        else:
            assert identity_service is not None
            self._identity_resolver_factory = lambda: identity_service
        self._message_sender = message_sender
        self._command_router = command_router or CommandRouter()
        self._service_command_handler = service_command_handler or ServiceCommandHandler()
        self._allowed_update_types = frozenset(allowed_update_types)
        self._lock_guard = asyncio.Lock()
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock_users: dict[str, int] = {}

    async def dispatch(self, update: MaxIncomingUpdate) -> DispatchOutcome:
        if update.update_type not in self._allowed_update_types:
            return DispatchOutcome(status=DispatchStatus.IGNORED, update_type=update.update_type)

        if update.chat_id is None:
            return DispatchOutcome(status=DispatchStatus.IGNORED, update_type=update.update_type)

        lock = await self._acquire_lock(update.chat_id)
        try:
            async with lock:
                return await self._dispatch_locked(update)
        finally:
            await self._release_lock(update.chat_id)

    async def _dispatch_locked(self, update: MaxIncomingUpdate) -> DispatchOutcome:
        chat_id = update.chat_id
        if chat_id is None:
            return DispatchOutcome(status=DispatchStatus.IGNORED, update_type=update.update_type)

        if update.chat_type != "PRIVATE":
            await self._send_with_policy(chat_id, GROUP_UNSUPPORTED_TEXT)
            return DispatchOutcome(
                status=DispatchStatus.RESPONDED,
                update_type=update.update_type,
                response_sent=True,
            )

        if update.max_user_id is None:
            return DispatchOutcome(status=DispatchStatus.IGNORED, update_type=update.update_type)

        try:
            identity_resolver = self._identity_resolver_factory()
            identity = await identity_resolver.resolve_or_onboard_private_max_user(
                ResolveMaxIdentityInput(
                    max_user_id=update.max_user_id,
                    max_chat_id=chat_id,
                    chat_type="PRIVATE",
                )
            )
        except IdentityConflict:
            await self._send_with_policy(chat_id, IDENTITY_CONFLICT_TEXT)
            return DispatchOutcome(
                status=DispatchStatus.RESPONDED,
                update_type=update.update_type,
                response_sent=True,
            )
        except (PersistenceConflict, UserDisabled) as exc:
            raise WebhookRetryableDispatchError("MAX dispatch identity unavailable") from exc

        command = self._command_for_update(update)
        if command is None:
            return DispatchOutcome(
                status=DispatchStatus.IGNORED,
                update_type=update.update_type,
                identity_resolved=True,
            )

        action = await self._service_command_handler.handle(
            ServiceCommandContext(
                command=command,
                identity=identity,
                max_user_id=update.max_user_id,
                max_chat_id=chat_id,
            )
        )
        status = await self._send_action_with_policy(chat_id, action)
        return DispatchOutcome(
            status=status,
            update_type=update.update_type,
            command=command,
            identity_resolved=True,
            response_sent=status is DispatchStatus.RESPONDED,
        )

    def _command_for_update(self, update: MaxIncomingUpdate) -> MaxServiceCommand | None:
        if update.update_type == "bot_started":
            return MaxServiceCommand.START
        if update.update_type == "message_created":
            return self._command_router.route(update.message_text).command
        if update.update_type == "message_callback":
            return None
        return None

    async def _send_action_with_policy(
        self,
        chat_id: str,
        action: ServiceCommandAction,
    ) -> DispatchStatus:
        try:
            if action.kind == "open_app":
                assert action.context_ref is not None
                assert action.label is not None
                await self._message_sender.send_open_app_to_chat(
                    chat_id=chat_id,
                    text=action.text,
                    context_ref=action.context_ref,
                    label=action.label,
                    app_path=action.app_path,
                )
            else:
                await self._message_sender.send_text_to_chat(chat_id=chat_id, text=action.text)
        except MaxApiError as exc:
            if exc.retryable:
                raise WebhookRetryableDispatchError("MAX outbound retryable failure") from exc
            return DispatchStatus.OUTBOUND_NON_RETRYABLE_FAILURE
        return DispatchStatus.RESPONDED

    async def _send_with_policy(self, chat_id: str, text: str) -> DispatchStatus:
        return await self._send_action_with_policy(
            chat_id,
            ServiceCommandAction.text_reply(text),
        )

    async def _acquire_lock(self, chat_id: str) -> asyncio.Lock:
        async with self._lock_guard:
            lock = self._locks.get(chat_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[chat_id] = lock
                self._lock_users[chat_id] = 0
            self._lock_users[chat_id] += 1
            return lock

    async def _release_lock(self, chat_id: str) -> None:
        async with self._lock_guard:
            remaining = self._lock_users.get(chat_id, 0) - 1
            if remaining <= 0:
                self._lock_users.pop(chat_id, None)
                self._locks.pop(chat_id, None)
            else:
                self._lock_users[chat_id] = remaining


__all__ = [
    "DispatchOutcome",
    "DispatchStatus",
    "IdentityResolver",
    "IdentityResolverFactory",
    "MessageSender",
    "UpdateDispatcher",
    "WebhookRetryableDispatchError",
]
