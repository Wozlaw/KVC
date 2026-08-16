"""MAX Long Polling development transport."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from kvc_integrations.max.client import MaxBotApiClient
from kvc_integrations.max.dto import MaxIncomingUpdate, MaxUpdatesBatch
from kvc_integrations.max.errors import MaxApiError
from kvc_integrations.max.update_parser import parse_max_update

SleepCallable = Callable[[float], Awaitable[None]]


class UpdateDispatch(Protocol):
    """Provider-neutral dispatcher contract consumed by the polling runner."""

    async def dispatch(self, update: MaxIncomingUpdate) -> object: ...


@dataclass(frozen=True)
class MaxLongPollingRunResult:
    """Safe testable result for a bounded Long Polling run."""

    cycles: int
    marker: str | None


class MaxLongPollingSource:
    """Development adapter for MAX GET /updates."""

    def __init__(
        self,
        api_client: MaxBotApiClient,
        *,
        limit: int,
        timeout_seconds: int,
        update_types: tuple[str, ...],
    ) -> None:
        self._api_client = api_client
        self._limit = limit
        self._timeout_seconds = timeout_seconds
        self._update_types = update_types

    async def get_updates(self, marker: str | None) -> MaxUpdatesBatch:
        """Fetch one provider update batch."""

        return await self._api_client.get_updates(
            marker=marker,
            limit=self._limit,
            timeout_seconds=self._timeout_seconds,
            update_types=self._update_types,
        )


class MaxLongPollingRunner:
    """Run Long Polling and feed updates into the shared dispatcher."""

    def __init__(
        self,
        *,
        source: MaxLongPollingSource,
        dispatcher: UpdateDispatch,
        sleep: SleepCallable = asyncio.sleep,
        initial_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 30.0,
    ) -> None:
        self._source = source
        self._dispatcher = dispatcher
        self._sleep = sleep
        self._initial_backoff_seconds = initial_backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds
        self.marker: str | None = None

    async def run(
        self,
        *,
        stop_event: asyncio.Event | None = None,
        max_cycles: int | None = None,
    ) -> MaxLongPollingRunResult:
        """Run polling until stopped, cancelled, or a test cycle limit is reached."""

        cycles = 0
        backoff_seconds = self._initial_backoff_seconds
        while not _is_stopped(stop_event) and (max_cycles is None or cycles < max_cycles):
            cycles += 1
            try:
                batch = await self._source.get_updates(self.marker)
            except asyncio.CancelledError:
                raise
            except MaxApiError as exc:
                if not exc.retryable:
                    raise
                await self._sleep_for(
                    _retry_delay(exc, backoff_seconds, self._max_backoff_seconds),
                    stop_event,
                )
                backoff_seconds = min(backoff_seconds * 2, self._max_backoff_seconds)
                continue

            await self._dispatch_batch(batch)
            self.marker = batch.marker
            backoff_seconds = self._initial_backoff_seconds

        return MaxLongPollingRunResult(cycles=cycles, marker=self.marker)

    async def _dispatch_batch(self, batch: MaxUpdatesBatch) -> None:
        for raw_update in batch.updates:
            update = parse_max_update(raw_update, source="long_polling")
            await self._dispatcher.dispatch(update)

    async def _sleep_for(
        self,
        delay_seconds: float,
        stop_event: asyncio.Event | None,
    ) -> None:
        if stop_event is not None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay_seconds)
            except TimeoutError:
                return
            return
        await self._sleep(delay_seconds)


def _is_stopped(stop_event: asyncio.Event | None) -> bool:
    return stop_event is not None and stop_event.is_set()


def _retry_delay(exc: MaxApiError, backoff_seconds: float, max_backoff_seconds: float) -> float:
    if exc.retry_after_seconds is not None:
        return min(float(exc.retry_after_seconds), max_backoff_seconds)
    return min(backoff_seconds, max_backoff_seconds)


__all__ = [
    "MaxLongPollingRunResult",
    "MaxLongPollingRunner",
    "MaxLongPollingSource",
    "SleepCallable",
    "UpdateDispatch",
]
