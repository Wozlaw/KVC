"""System clock adapter."""

from __future__ import annotations

from datetime import UTC, datetime


class UtcClock:
    """Clock adapter returning timezone-aware UTC datetimes."""

    def now(self) -> datetime:
        return datetime.now(UTC)
