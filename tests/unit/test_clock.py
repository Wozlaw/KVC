"""System clock adapter tests."""

from __future__ import annotations

from datetime import timedelta

from kvc_integrations.system import UtcClock


def test_utc_clock_returns_timezone_aware_utc_datetime() -> None:
    now = UtcClock().now()

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
