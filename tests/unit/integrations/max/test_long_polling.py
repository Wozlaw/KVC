"""MAX Long Polling source/runner tests."""

from __future__ import annotations

import asyncio

import pytest

from kvc_api.max.dispatcher import WebhookRetryableDispatchError
from kvc_integrations.max import MaxLongPollingRunner, MaxUpdatesBatch
from kvc_integrations.max.dto import MaxIncomingUpdate
from kvc_integrations.max.errors import MaxApiAuthenticationError, MaxApiRateLimitError


def raw_private_update(text: str = "/start") -> dict[str, object]:
    return {
        "update_type": "message_created",
        "timestamp": 1_700_000_000_000,
        "message": {
            "sender": {"user_id": 123},
            "recipient": {"chat_id": 456, "chat_type": "dialog"},
            "body": {"mid": "mid-1", "text": text},
        },
    }


class FakeSource:
    def __init__(self, events: list[MaxUpdatesBatch | BaseException]) -> None:
        self.events = events
        self.markers: list[str | None] = []

    async def get_updates(self, marker: str | None) -> MaxUpdatesBatch:
        self.markers.append(marker)
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event


class FakeDispatcher:
    def __init__(self, *, exc: Exception | None = None) -> None:
        self.calls: list[MaxIncomingUpdate] = []
        self.exc = exc

    async def dispatch(self, update: MaxIncomingUpdate) -> object:
        self.calls.append(update)
        if self.exc is not None:
            raise self.exc
        return object()


@pytest.mark.asyncio
async def test_long_polling_runner_reuses_parser_and_dispatcher_with_marker_progression() -> None:
    source = FakeSource(
        [
            MaxUpdatesBatch(updates=(raw_private_update("/start"),), marker="10"),
            MaxUpdatesBatch(updates=(raw_private_update("/help"),), marker="20"),
        ]
    )
    dispatcher = FakeDispatcher()

    result = await MaxLongPollingRunner(source=source, dispatcher=dispatcher).run(max_cycles=2)

    assert source.markers == [None, "10"]
    assert result.marker == "20"
    assert [call.source for call in dispatcher.calls] == ["long_polling", "long_polling"]
    assert [call.message_text for call in dispatcher.calls] == ["/start", "/help"]


@pytest.mark.asyncio
async def test_long_polling_runner_empty_batch_advances_marker_without_dispatch() -> None:
    source = FakeSource([MaxUpdatesBatch(updates=(), marker="10")])
    dispatcher = FakeDispatcher()

    result = await MaxLongPollingRunner(source=source, dispatcher=dispatcher).run(max_cycles=1)

    assert result.marker == "10"
    assert dispatcher.calls == []


@pytest.mark.asyncio
async def test_long_polling_runner_does_not_advance_marker_on_dispatch_failure() -> None:
    source = FakeSource([MaxUpdatesBatch(updates=(raw_private_update(),), marker="10")])
    dispatcher = FakeDispatcher(exc=WebhookRetryableDispatchError("retry"))
    runner = MaxLongPollingRunner(source=source, dispatcher=dispatcher)

    with pytest.raises(WebhookRetryableDispatchError):
        await runner.run(max_cycles=1)

    assert runner.marker is None


@pytest.mark.asyncio
async def test_long_polling_runner_retries_provider_get_with_bounded_delay_only() -> None:
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    source = FakeSource(
        [
            MaxApiRateLimitError("rate", status_code=429, retry_after_seconds=100),
            MaxUpdatesBatch(updates=(), marker="10"),
        ]
    )
    dispatcher = FakeDispatcher()

    result = await MaxLongPollingRunner(
        source=source,
        dispatcher=dispatcher,
        sleep=record_sleep,
        max_backoff_seconds=30,
    ).run(max_cycles=2)

    assert delays == [30]
    assert source.markers == [None, None]
    assert result.marker == "10"
    assert dispatcher.calls == []


@pytest.mark.asyncio
async def test_long_polling_runner_stop_event_interrupts_retry_sleep() -> None:
    stop_event = asyncio.Event()

    class StoppingSource(FakeSource):
        async def get_updates(self, marker: str | None) -> MaxUpdatesBatch:
            stop_event.set()
            return await super().get_updates(marker)

    source = StoppingSource([MaxApiRateLimitError("rate", status_code=429)])
    dispatcher = FakeDispatcher()

    result = await MaxLongPollingRunner(source=source, dispatcher=dispatcher).run(
        stop_event=stop_event,
        max_cycles=2,
    )

    assert result.cycles == 1
    assert result.marker is None


@pytest.mark.asyncio
async def test_long_polling_runner_stops_on_non_retryable_provider_error() -> None:
    source = FakeSource([MaxApiAuthenticationError("auth", status_code=401)])
    dispatcher = FakeDispatcher()

    with pytest.raises(MaxApiAuthenticationError):
        await MaxLongPollingRunner(source=source, dispatcher=dispatcher).run(max_cycles=1)


@pytest.mark.asyncio
async def test_long_polling_runner_propagates_cancellation() -> None:
    source = FakeSource([asyncio.CancelledError()])
    dispatcher = FakeDispatcher()

    with pytest.raises(asyncio.CancelledError):
        await MaxLongPollingRunner(source=source, dispatcher=dispatcher).run(max_cycles=1)
