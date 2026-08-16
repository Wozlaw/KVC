"""Shared MAX runtime composition helpers."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kvc_api.max.command_router import CommandRouter
from kvc_api.max.dispatcher import UpdateDispatcher
from kvc_application.services import IdentityService
from kvc_config import AppSettings
from kvc_integrations.max import MaxBotApiClient, MaxMessageSender


class MaxRuntimeConfigurationError(RuntimeError):
    """Raised when MAX runtime dependencies cannot be built safely."""


@dataclass(frozen=True)
class MaxRuntime:
    """Runtime objects shared by webhook and Long Polling transports."""

    dispatcher: UpdateDispatcher
    message_sender: MaxMessageSender
    api_client: MaxBotApiClient


def build_max_dispatcher(
    *,
    sessionmaker: async_sessionmaker[AsyncSession],
    message_sender: MaxMessageSender,
    allowed_update_types: tuple[str, ...],
) -> UpdateDispatcher:
    """Build the shared MAX dispatcher with per-dispatch identity service scope."""

    return UpdateDispatcher(
        identity_resolver_factory=lambda: IdentityService(sessionmaker),
        message_sender=message_sender,
        command_router=CommandRouter(),
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
    dispatcher = build_max_dispatcher(
        sessionmaker=sessionmaker,
        message_sender=message_sender,
        allowed_update_types=settings.max_allowed_update_types,
    )
    return MaxRuntime(
        dispatcher=dispatcher,
        message_sender=message_sender,
        api_client=api_client,
    )


__all__ = [
    "MaxRuntime",
    "MaxRuntimeConfigurationError",
    "build_max_dispatcher",
    "build_max_runtime",
]
