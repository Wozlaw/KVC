"""Final MAX service-command orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from kvc_api.max.command_router import MaxServiceCommand
from kvc_api.max.response_text import (
    CONNECT_ALREADY_ACTIVE_TEXT,
    CONNECT_DISABLED_TEXT,
    CONNECT_NEEDS_REAUTH_TEXT,
    CONNECT_OPEN_LABEL,
    CONNECT_OPEN_TEXT,
    CONNECTION_ACTIVE_TEXT,
    CONNECTION_DISABLED_TEXT,
    CONNECTION_MISSING_TEXT,
    CONNECTION_NEEDS_REAUTH_TEXT,
    DISABLE_MISSING_TEXT,
    DISABLE_SUCCESS_TEXT,
    HELP_TEXT,
    MINI_APP_UNAVAILABLE_TEXT,
    NON_COMMAND_TEXT,
    NOTIFICATIONS_LATER_TEXT,
    RECONNECT_MISSING_TEXT,
    RECONNECT_OPEN_LABEL,
    RECONNECT_OPEN_TEXT,
    START_CONNECTED_TEXT,
    START_DISABLED_CONNECTION_TEXT,
    START_MISSING_CONNECTION_TEXT,
    START_NEEDS_REAUTH_TEXT,
    TEMPORARY_ERROR_TEXT,
    UNKNOWN_COMMAND_TEXT,
    USER_DISABLED_TEXT,
)
from kvc_application.dto import IdentityResolution, KaitenConnectionResult
from kvc_application.errors import KaitenConnectionMissing, PersistenceConflict
from kvc_integrations.max.context_signing import MiniAppContextPurpose, MiniAppContextSigner

CONNECT_CONTEXT_TTL_SECONDS = 900


class KaitenConnectionDisabler(Protocol):
    """Minimal application-service contract for disabling a Kaiten connection."""

    async def disable_connection(self, user_id: UUID) -> KaitenConnectionResult: ...


@dataclass(frozen=True)
class ServiceCommandContext:
    """Trusted command context after provider parsing and identity resolution."""

    command: MaxServiceCommand
    identity: IdentityResolution
    max_user_id: str
    max_chat_id: str


@dataclass(frozen=True)
class ServiceCommandAction:
    """Outbound action requested by the service-command handler."""

    kind: Literal["text", "open_app"]
    text: str
    context_ref: str | None = None
    label: str | None = None

    @classmethod
    def text_reply(cls, text: str) -> ServiceCommandAction:
        return cls(kind="text", text=text)

    @classmethod
    def open_app(cls, *, text: str, context_ref: str, label: str) -> ServiceCommandAction:
        return cls(kind="open_app", text=text, context_ref=context_ref, label=label)


class ServiceCommandHandler:
    """Execute final branch-004 service-command UX after identity resolution."""

    def __init__(
        self,
        *,
        context_signer: MiniAppContextSigner | None = None,
        kaiten_connection_service_factory: Callable[[], KaitenConnectionDisabler] | None = None,
        mini_app_launch_enabled: bool = False,
        now: Callable[[], int] | None = None,
    ) -> None:
        self._context_signer = context_signer
        self._kaiten_connection_service_factory = kaiten_connection_service_factory
        self._mini_app_launch_enabled = mini_app_launch_enabled
        self._now = now or (lambda: int(time.time()))

    async def handle(self, context: ServiceCommandContext) -> ServiceCommandAction:
        if context.command is MaxServiceCommand.START:
            return ServiceCommandAction.text_reply(self._start_text(context.identity))
        if context.command is MaxServiceCommand.HELP:
            return ServiceCommandAction.text_reply(
                HELP_TEXT
                if context.identity.user_status == "ACTIVE"
                else f"{USER_DISABLED_TEXT}\n\n{HELP_TEXT}"
            )
        if context.command is MaxServiceCommand.CONNECT:
            return self._connect_action(context)
        if context.command is MaxServiceCommand.RECONNECT:
            return self._reconnect_action(context)
        if context.command is MaxServiceCommand.CONNECTION:
            return ServiceCommandAction.text_reply(self._connection_text(context.identity))
        if context.command is MaxServiceCommand.DISABLE:
            return await self._disable_action(context)
        if context.command is MaxServiceCommand.NOTIFICATIONS:
            return ServiceCommandAction.text_reply(NOTIFICATIONS_LATER_TEXT)
        if context.command is MaxServiceCommand.NON_COMMAND:
            return ServiceCommandAction.text_reply(NON_COMMAND_TEXT)
        return ServiceCommandAction.text_reply(UNKNOWN_COMMAND_TEXT)

    def _start_text(self, identity: IdentityResolution) -> str:
        if identity.user_status == "DISABLED":
            return USER_DISABLED_TEXT
        status = identity.kaiten_connection_status
        if status is None:
            return START_MISSING_CONNECTION_TEXT
        if status == "ACTIVE":
            return START_CONNECTED_TEXT
        if status == "NEEDS_REAUTH":
            return START_NEEDS_REAUTH_TEXT
        return START_DISABLED_CONNECTION_TEXT

    def _connect_action(self, context: ServiceCommandContext) -> ServiceCommandAction:
        if context.identity.user_status == "DISABLED":
            return ServiceCommandAction.text_reply(USER_DISABLED_TEXT)
        status = context.identity.kaiten_connection_status
        if status == "ACTIVE":
            return ServiceCommandAction.text_reply(CONNECT_ALREADY_ACTIVE_TEXT)
        if status == "NEEDS_REAUTH":
            return ServiceCommandAction.text_reply(CONNECT_NEEDS_REAUTH_TEXT)
        if status == "DISABLED":
            return ServiceCommandAction.text_reply(CONNECT_DISABLED_TEXT)
        return self._open_app_action(
            context,
            purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            text=CONNECT_OPEN_TEXT,
            label=CONNECT_OPEN_LABEL,
        )

    def _reconnect_action(self, context: ServiceCommandContext) -> ServiceCommandAction:
        if context.identity.user_status == "DISABLED":
            return ServiceCommandAction.text_reply(USER_DISABLED_TEXT)
        if context.identity.kaiten_connection_status is None:
            return ServiceCommandAction.text_reply(RECONNECT_MISSING_TEXT)
        return self._open_app_action(
            context,
            purpose=MiniAppContextPurpose.RECONNECT_KAITEN,
            text=RECONNECT_OPEN_TEXT,
            label=RECONNECT_OPEN_LABEL,
        )

    def _open_app_action(
        self,
        context: ServiceCommandContext,
        *,
        purpose: MiniAppContextPurpose,
        text: str,
        label: str,
    ) -> ServiceCommandAction:
        if not self._mini_app_launch_enabled or self._context_signer is None:
            return ServiceCommandAction.text_reply(MINI_APP_UNAVAILABLE_TEXT)
        binding = self._context_signer.make_identity_binding(
            max_user_id=context.max_user_id,
            chat_id=context.max_chat_id,
        )
        context_ref = self._context_signer.issue(
            purpose=purpose,
            identity_binding=binding,
            ttl_seconds=CONNECT_CONTEXT_TTL_SECONDS,
            now=self._now(),
        )
        return ServiceCommandAction.open_app(text=text, context_ref=context_ref, label=label)

    def _connection_text(self, identity: IdentityResolution) -> str:
        status = identity.kaiten_connection_status
        if status is None:
            return CONNECTION_MISSING_TEXT
        if status == "ACTIVE":
            return CONNECTION_ACTIVE_TEXT
        if status == "NEEDS_REAUTH":
            return CONNECTION_NEEDS_REAUTH_TEXT
        return CONNECTION_DISABLED_TEXT

    async def _disable_action(self, context: ServiceCommandContext) -> ServiceCommandAction:
        if context.identity.user_status == "DISABLED":
            return ServiceCommandAction.text_reply(USER_DISABLED_TEXT)
        if context.identity.kaiten_connection_status is None:
            return ServiceCommandAction.text_reply(DISABLE_MISSING_TEXT)
        if self._kaiten_connection_service_factory is None:
            return ServiceCommandAction.text_reply(TEMPORARY_ERROR_TEXT)
        try:
            await self._kaiten_connection_service_factory().disable_connection(
                context.identity.user_id
            )
        except KaitenConnectionMissing:
            return ServiceCommandAction.text_reply(DISABLE_MISSING_TEXT)
        except PersistenceConflict:
            return ServiceCommandAction.text_reply(TEMPORARY_ERROR_TEXT)
        return ServiceCommandAction.text_reply(DISABLE_SUCCESS_TEXT)


__all__ = [
    "CONNECT_CONTEXT_TTL_SECONDS",
    "KaitenConnectionDisabler",
    "ServiceCommandAction",
    "ServiceCommandContext",
    "ServiceCommandHandler",
]
