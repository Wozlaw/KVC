"""Development MAX Long Polling worker entrypoint."""

from __future__ import annotations

import asyncio
import sys

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from kvc_api.max.runtime import (
    MaxRuntimeConfigurationError,
    build_max_runtime,
)
from kvc_config import AppSettings, get_settings
from kvc_integrations.max import (
    MaxLongPollingRunner,
    MaxLongPollingRunResult,
    MaxLongPollingSource,
    SleepCallable,
)
from kvc_persistence import (
    DatabaseConfigurationError,
    create_async_engine_from_settings,
    create_async_sessionmaker,
    dispose_async_engine,
)


class WorkerConfigurationError(RuntimeError):
    """Raised when the worker cannot start the selected runtime safely."""


async def run_long_polling_worker(
    settings: AppSettings | None = None,
    *,
    http_client: httpx.AsyncClient | None = None,
    engine: AsyncEngine | None = None,
    stop_event: asyncio.Event | None = None,
    max_cycles: int | None = None,
    sleep: SleepCallable = asyncio.sleep,
) -> MaxLongPollingRunResult:
    """Run the explicit development Long Polling worker."""

    app_settings = settings or get_settings()
    if app_settings.max_inbound_mode != "long_polling":
        raise WorkerConfigurationError(
            "MAX Long Polling worker requires KVC_MAX_INBOUND_MODE=long_polling."
        )
    if app_settings.max_bot_token is None:
        raise WorkerConfigurationError("KVC_MAX_BOT_TOKEN is required for Long Polling.")

    owns_http_client = http_client is None
    owns_engine = engine is None
    owned_http_client: httpx.AsyncClient | None = None
    owned_engine: AsyncEngine | None = None
    try:
        owned_http_client = http_client or httpx.AsyncClient()
        owned_engine = engine or create_async_engine_from_settings(app_settings)
        sessionmaker = create_async_sessionmaker(owned_engine)
        runtime = build_max_runtime(
            settings=app_settings,
            http_client=owned_http_client,
            sessionmaker=sessionmaker,
        )
        source = MaxLongPollingSource(
            runtime.api_client,
            limit=app_settings.max_polling_limit,
            timeout_seconds=app_settings.max_polling_timeout_seconds,
            update_types=app_settings.max_allowed_update_types,
        )
        runner = MaxLongPollingRunner(
            source=source,
            dispatcher=runtime.dispatcher,
            sleep=sleep,
        )
        return await runner.run(stop_event=stop_event, max_cycles=max_cycles)
    except MaxRuntimeConfigurationError as exc:
        raise WorkerConfigurationError(str(exc)) from exc
    except DatabaseConfigurationError as exc:
        raise WorkerConfigurationError(str(exc)) from exc
    finally:
        if owns_http_client and owned_http_client is not None:
            await owned_http_client.aclose()
        if owns_engine and owned_engine is not None:
            await dispose_async_engine(owned_engine)


def main() -> int:
    """Run the worker CLI."""

    try:
        asyncio.run(run_long_polling_worker())
    except KeyboardInterrupt:
        return 0
    except WorkerConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
