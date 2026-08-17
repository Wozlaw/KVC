"""Production ASGI composition root."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Protocol

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from kvc_api.main import create_app
from kvc_api.max.runtime import (
    MaxMiniAppRuntime,
    MaxRuntime,
    MaxRuntimeConfigurationError,
    build_max_mini_app_runtime,
    build_max_runtime,
)
from kvc_config import AppSettings, get_settings
from kvc_integrations.security import build_token_cipher
from kvc_persistence import (
    DatabaseConfigurationError,
    create_async_engine_from_settings,
    create_async_sessionmaker,
    dispose_async_engine,
    get_database_url,
)


class ProductionConfigurationError(RuntimeError):
    """Raised when production ASGI runtime cannot be safely composed."""


class HttpClientFactory(Protocol):
    """Factory protocol for owned production HTTP clients."""

    def __call__(self) -> httpx.AsyncClient: ...


class EngineFactory(Protocol):
    """Factory protocol for owned production database engines."""

    def __call__(self, settings: AppSettings) -> AsyncEngine: ...


class SessionmakerFactory(Protocol):
    """Factory protocol for production sessionmakers."""

    def __call__(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]: ...


class EngineDisposer(Protocol):
    """Async disposer protocol for owned production engines."""

    async def __call__(self, engine: AsyncEngine) -> None: ...


class MaxRuntimeBuilder(Protocol):
    """Factory protocol for shared MAX runtime composition."""

    def __call__(
        self,
        *,
        settings: AppSettings,
        http_client: httpx.AsyncClient,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> MaxRuntime: ...


class MaxMiniAppRuntimeBuilder(Protocol):
    """Factory protocol for MAX Mini App runtime composition."""

    def __call__(
        self,
        *,
        settings: AppSettings,
        http_client: httpx.AsyncClient,
        sessionmaker: async_sessionmaker[AsyncSession],
        message_sender: Any,
    ) -> MaxMiniAppRuntime: ...


def create_production_app(
    settings: AppSettings | None = None,
    *,
    http_client_factory: HttpClientFactory = httpx.AsyncClient,
    engine_factory: EngineFactory = create_async_engine_from_settings,
    sessionmaker_factory: SessionmakerFactory = create_async_sessionmaker,
    engine_disposer: EngineDisposer = dispose_async_engine,
    max_runtime_builder: MaxRuntimeBuilder = build_max_runtime,
    max_mini_app_runtime_builder: MaxMiniAppRuntimeBuilder = build_max_mini_app_runtime,
) -> FastAPI:
    """Compose the production FastAPI app with real owned runtime dependencies."""

    app_settings = settings or get_settings()
    _validate_production_settings(app_settings)

    http_client = http_client_factory()
    engine = engine_factory(app_settings)
    sessionmaker = sessionmaker_factory(engine)
    max_runtime = max_runtime_builder(
        settings=app_settings,
        http_client=http_client,
        sessionmaker=sessionmaker,
    )
    max_mini_app_runtime = max_mini_app_runtime_builder(
        settings=app_settings,
        http_client=http_client,
        sessionmaker=sessionmaker,
        message_sender=max_runtime.message_sender,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await http_client.aclose()
            await engine_disposer(engine)

    return create_app(
        app_settings,
        max_dispatcher=max_runtime.dispatcher,
        max_mini_app_runtime=max_mini_app_runtime,
        lifespan=lifespan,
    )


def _validate_production_settings(settings: AppSettings) -> None:
    missing = [
        name
        for name, value in (
            ("KVC_DATABASE_URL", settings.database_url),
            ("KVC_MAX_BOT_TOKEN", settings.max_bot_token),
            ("KVC_MAX_WEBHOOK_SECRET", settings.max_webhook_secret),
            ("KVC_MAX_WEBHOOK_PUBLIC_URL", settings.max_webhook_public_url),
            ("KVC_MAX_MINI_APP_PUBLIC_URL", settings.max_mini_app_public_url),
            ("KVC_MAX_MINI_APP_CONTEXT_SECRET", settings.max_mini_app_context_secret),
            ("KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION", settings.token_encryption_active_version),
            ("KVC_TOKEN_ENCRYPTION_KEYS", settings.token_encryption_keys),
        )
        if value is None
    ]
    if missing:
        raise ProductionConfigurationError(
            "Missing production configuration: " + ", ".join(missing)
        )
    if settings.max_inbound_mode != "webhook":
        raise ProductionConfigurationError(
            "Production ASGI runtime requires KVC_MAX_INBOUND_MODE=webhook."
        )
    if not settings.max_allowed_update_types:
        raise ProductionConfigurationError(
            "KVC_MAX_ALLOWED_UPDATE_TYPES must not be empty for production runtime."
        )
    if not settings.max_webhook_path:
        raise ProductionConfigurationError(
            "KVC_MAX_WEBHOOK_PATH is required for production runtime."
        )
    try:
        get_database_url(settings)
    except DatabaseConfigurationError as exc:
        raise ProductionConfigurationError(str(exc)) from exc
    if settings.max_api_base_url.strip() == "":
        raise ProductionConfigurationError("KVC_MAX_API_BASE_URL is required.")
    try:
        _validate_https_public_url(
            settings.max_webhook_public_url,
            setting_name="KVC_MAX_WEBHOOK_PUBLIC_URL",
            allow_query=False,
        )
        _validate_https_public_url(
            settings.max_mini_app_public_url,
            setting_name="KVC_MAX_MINI_APP_PUBLIC_URL",
            allow_query=True,
        )
        build_token_cipher(settings)
    except (MaxRuntimeConfigurationError, ValueError) as exc:
        raise ProductionConfigurationError(str(exc)) from exc


def _validate_https_public_url(
    value: str | None,
    *,
    setting_name: str,
    allow_query: bool,
) -> None:
    if value is None:
        raise ProductionConfigurationError(f"{setting_name} is required.")
    try:
        url = httpx.URL(value)
    except httpx.InvalidURL as exc:
        raise ProductionConfigurationError(
            f"{setting_name} must be a safe HTTPS public URL."
        ) from exc
    if (
        url.scheme != "https"
        or url.host is None
        or url.userinfo
        or url.fragment
        or (url.port not in {None, 443})
        or (not allow_query and url.query)
    ):
        raise ProductionConfigurationError(f"{setting_name} must be a safe HTTPS public URL.")


__all__ = ["ProductionConfigurationError", "create_production_app"]
