"""MAX worker/runtime composition tests."""

from __future__ import annotations

from unittest.mock import Mock

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kvc_api.max import MaxRuntime, UpdateDispatcher, build_max_runtime
from kvc_config import AppSettings
from kvc_worker.__main__ import WorkerConfigurationError, run_long_polling_worker

TOKEN_MARKER = "SYNTHETIC-MAX-WORKER-TOKEN"


def long_polling_settings() -> AppSettings:
    return AppSettings(
        max_inbound_mode="long_polling",
        max_bot_token=SecretStr(TOKEN_MARKER),
        database_url=SecretStr("postgresql+asyncpg://kvc:kvc@localhost/kvc_dev"),
    )


@pytest.mark.asyncio
async def test_build_max_runtime_uses_shared_dispatcher_contract_without_mini_app_url() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200))
    ) as http_client:
        runtime = build_max_runtime(
            settings=long_polling_settings(),
            http_client=http_client,
            sessionmaker=async_sessionmaker(),
        )

    assert isinstance(runtime, MaxRuntime)
    assert isinstance(runtime.dispatcher, UpdateDispatcher)
    assert TOKEN_MARKER not in repr(runtime.api_client)
    assert "redacted" in repr(runtime.message_sender)


@pytest.mark.asyncio
async def test_long_polling_worker_requires_long_polling_mode() -> None:
    with pytest.raises(WorkerConfigurationError) as caught:
        await run_long_polling_worker(
            AppSettings(max_inbound_mode="webhook", max_bot_token=SecretStr(TOKEN_MARKER)),
            max_cycles=0,
        )

    assert "long_polling" in str(caught.value)
    assert TOKEN_MARKER not in str(caught.value)


@pytest.mark.asyncio
async def test_long_polling_worker_requires_bot_token() -> None:
    with pytest.raises(WorkerConfigurationError) as caught:
        await run_long_polling_worker(
            AppSettings(_env_file=None, max_inbound_mode="long_polling"),
            max_cycles=0,
        )

    assert "KVC_MAX_BOT_TOKEN" in str(caught.value)


@pytest.mark.asyncio
async def test_long_polling_worker_builds_explicit_runtime_without_polling_in_zero_cycle_run() -> (
    None
):
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, json={"updates": [], "marker": None})

    engine = Mock(spec=AsyncEngine)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        result = await run_long_polling_worker(
            long_polling_settings(),
            http_client=http_client,
            engine=engine,
            max_cycles=0,
        )

        assert http_client.is_closed is False

    assert result.cycles == 0
    assert result.marker is None
    assert request_count == 0
