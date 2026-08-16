"""Shared MAX runtime composition helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kvc_api.max.command_router import CommandRouter
from kvc_api.max.dispatcher import UpdateDispatcher
from kvc_api.max.service_commands import KaitenConnectionDisabler, ServiceCommandHandler
from kvc_application.dto import (
    BindKaitenConnectionInput,
    IdentityResolution,
    KaitenConnectionResult,
    ResolveMaxIdentityInput,
)
from kvc_application.services import IdentityService, KaitenConnectionService
from kvc_config import AppSettings
from kvc_integrations.kaiten import KaitenHttpCredentialVerifier
from kvc_integrations.max import MaxBotApiClient, MaxMessageSender, MiniAppContextSigner
from kvc_integrations.security import build_token_cipher
from kvc_integrations.system.clock import UtcClock


class MaxRuntimeConfigurationError(RuntimeError):
    """Raised when MAX runtime dependencies cannot be built safely."""


@dataclass(frozen=True)
class MaxRuntime:
    """Runtime objects shared by webhook and Long Polling transports."""

    dispatcher: UpdateDispatcher
    message_sender: MaxMessageSender
    api_client: MaxBotApiClient


class MaxIdentityResolver(Protocol):
    """Application identity resolver used by MAX presentation adapters."""

    async def resolve_or_onboard_private_max_user(
        self,
        input: ResolveMaxIdentityInput,
    ) -> IdentityResolution: ...


class KaitenConnectionBinder(Protocol):
    """Kaiten credential binder used by MAX Mini App presentation."""

    async def bind_or_replace_connection(
        self,
        input: BindKaitenConnectionInput,
    ) -> KaitenConnectionResult: ...


class MaxMessageConfirmationSender(Protocol):
    """Minimal outbound MAX confirmation contract for Mini App routes."""

    async def send_text_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        notify: bool = True,
    ) -> object: ...


@dataclass(frozen=True)
class MaxMiniAppRuntime:
    """Request-scoped service factories for MAX Mini App routes."""

    identity_resolver_factory: Callable[[], MaxIdentityResolver]
    kaiten_connection_binder_factory: Callable[[], KaitenConnectionBinder]
    message_sender: MaxMessageConfirmationSender
    context_signer: MiniAppContextSigner


def build_max_dispatcher(
    *,
    sessionmaker: async_sessionmaker[AsyncSession],
    message_sender: MaxMessageSender,
    allowed_update_types: tuple[str, ...],
    context_signer: MiniAppContextSigner | None = None,
    kaiten_connection_service_factory: Callable[[], KaitenConnectionDisabler] | None = None,
    mini_app_launch_enabled: bool = False,
) -> UpdateDispatcher:
    """Build the shared MAX dispatcher with per-dispatch identity service scope."""

    return UpdateDispatcher(
        identity_resolver_factory=lambda: IdentityService(sessionmaker),
        message_sender=message_sender,
        command_router=CommandRouter(),
        service_command_handler=ServiceCommandHandler(
            context_signer=context_signer,
            kaiten_connection_service_factory=kaiten_connection_service_factory,
            mini_app_launch_enabled=mini_app_launch_enabled,
        ),
        allowed_update_types=allowed_update_types,
    )


def build_max_runtime(
    *,
    settings: AppSettings,
    http_client: httpx.AsyncClient,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> MaxRuntime:
    """Build MAX runtime dependencies without owning their external lifecycles."""

    if settings.max_bot_token is None:
        raise MaxRuntimeConfigurationError("KVC_MAX_BOT_TOKEN is required for MAX runtime.")

    api_client = MaxBotApiClient(
        http_client,
        bot_token=settings.max_bot_token,
        api_base_url=settings.max_api_base_url,
    )
    message_sender = MaxMessageSender(
        api_client,
        mini_app_public_url=settings.max_mini_app_public_url,
    )
    context_signer = (
        None
        if settings.max_mini_app_context_secret is None
        else MiniAppContextSigner(settings.max_mini_app_context_secret)
    )
    token_cipher = None
    if (
        settings.token_encryption_active_version is not None
        and settings.token_encryption_keys is not None
    ):
        token_cipher = build_token_cipher(settings)
    kaiten_connection_service_factory = (
        None
        if token_cipher is None
        else lambda: KaitenConnectionService(
            sessionmaker,
            KaitenHttpCredentialVerifier(http_client),
            token_cipher,
            UtcClock(),
        )
    )
    dispatcher = build_max_dispatcher(
        sessionmaker=sessionmaker,
        message_sender=message_sender,
        allowed_update_types=settings.max_allowed_update_types,
        context_signer=context_signer,
        kaiten_connection_service_factory=kaiten_connection_service_factory,
        mini_app_launch_enabled=(
            context_signer is not None and settings.max_mini_app_public_url is not None
        ),
    )
    return MaxRuntime(
        dispatcher=dispatcher,
        message_sender=message_sender,
        api_client=api_client,
    )


__all__ = [
    "KaitenConnectionBinder",
    "MaxIdentityResolver",
    "MaxMessageConfirmationSender",
    "MaxMiniAppRuntime",
    "MaxRuntime",
    "MaxRuntimeConfigurationError",
    "build_max_dispatcher",
    "build_max_runtime",
]
