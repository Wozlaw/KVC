"""Shared MAX runtime composition helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kvc_api.max.command_router import CommandRouter
from kvc_api.max.dispatcher import UpdateDispatcher
from kvc_api.max.service_commands import KaitenConnectionDisabler, ServiceCommandHandler
from kvc_application.dto import (
    BindKaitenConnectionInput,
    IdentityResolution,
    KaitenConnectionResult,
    NotificationSettingsResult,
    ResolveMaxIdentityInput,
    UpdateNotificationSettingsInput,
)
from kvc_application.ports import ContextInteractionResolver
from kvc_application.services import (
    IdentityService,
    KaitenConnectionService,
    NotificationSettingsService,
)
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


class NotificationSettingsManager(Protocol):
    """Notification settings service contract for MAX Mini App routes."""

    async def get_settings(self, user_id: UUID) -> NotificationSettingsResult: ...

    async def update_settings(
        self,
        input: UpdateNotificationSettingsInput,
    ) -> NotificationSettingsResult: ...


@dataclass(frozen=True)
class MaxMiniAppRuntime:
    """Request-scoped service factories for MAX Mini App routes."""

    identity_resolver_factory: Callable[[], MaxIdentityResolver]
    kaiten_connection_binder_factory: Callable[[], KaitenConnectionBinder]
    message_sender: MaxMessageConfirmationSender
    context_signer: MiniAppContextSigner
    notification_settings_service_factory: Callable[[], NotificationSettingsManager] | None = None
    context_interaction_resolver_factory: Callable[[], ContextInteractionResolver] | None = None


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
    context_signer = _build_context_signer_or_none(settings)
    kaiten_connection_service_factory = _build_kaiten_connection_service_factory_or_none(
        settings=settings,
        http_client=http_client,
        sessionmaker=sessionmaker,
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


def build_max_mini_app_runtime(
    *,
    settings: AppSettings,
    http_client: httpx.AsyncClient,
    sessionmaker: async_sessionmaker[AsyncSession],
    message_sender: MaxMessageConfirmationSender,
    context_interaction_resolver_factory: Callable[[], ContextInteractionResolver] | None = None,
) -> MaxMiniAppRuntime:
    """Build real MAX Mini App runtime dependencies for production composition."""

    context_signer = _build_context_signer_or_none(settings)
    if context_signer is None:
        raise MaxRuntimeConfigurationError(
            "KVC_MAX_MINI_APP_CONTEXT_SECRET is required for MAX Mini App runtime."
        )
    kaiten_connection_service_factory = _build_kaiten_connection_service_factory_or_none(
        settings=settings,
        http_client=http_client,
        sessionmaker=sessionmaker,
    )
    if kaiten_connection_service_factory is None:
        raise MaxRuntimeConfigurationError(
            "KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION and KVC_TOKEN_ENCRYPTION_KEYS are required "
            "for MAX Mini App runtime."
        )

    return MaxMiniAppRuntime(
        identity_resolver_factory=lambda: IdentityService(sessionmaker),
        kaiten_connection_binder_factory=kaiten_connection_service_factory,
        message_sender=message_sender,
        context_signer=context_signer,
        notification_settings_service_factory=lambda: NotificationSettingsService(sessionmaker),
        context_interaction_resolver_factory=context_interaction_resolver_factory,
    )


def _build_context_signer_or_none(settings: AppSettings) -> MiniAppContextSigner | None:
    if settings.max_mini_app_context_secret is None:
        return None
    return MiniAppContextSigner(settings.max_mini_app_context_secret)


def _build_kaiten_connection_service_factory_or_none(
    *,
    settings: AppSettings,
    http_client: httpx.AsyncClient,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> Callable[[], KaitenConnectionService] | None:
    if settings.token_encryption_active_version is None or settings.token_encryption_keys is None:
        return None
    try:
        token_cipher = build_token_cipher(settings)
    except ValueError as exc:
        raise MaxRuntimeConfigurationError(str(exc)) from exc
    return lambda: KaitenConnectionService(
        sessionmaker,
        KaitenHttpCredentialVerifier(http_client),
        token_cipher,
        UtcClock(),
    )


__all__ = [
    "KaitenConnectionBinder",
    "MaxIdentityResolver",
    "MaxMessageConfirmationSender",
    "MaxMiniAppRuntime",
    "MaxRuntime",
    "MaxRuntimeConfigurationError",
    "build_max_mini_app_runtime",
    "build_max_dispatcher",
    "build_max_runtime",
]
