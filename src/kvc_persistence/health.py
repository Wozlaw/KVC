"""Database health probe."""

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause


class ScalarResult(Protocol):
    """Minimal result contract used by the health probe."""

    def scalar_one(self) -> object:
        """Return a single scalar value."""


class DatabaseConnection(Protocol):
    """Minimal async connection contract used by the health probe."""

    async def execute(self, statement: TextClause) -> ScalarResult:
        """Execute a SQL statement."""


class DatabaseConnectionContext(Protocol):
    """Async context manager returned by an engine connection factory."""

    async def __aenter__(self) -> DatabaseConnection:
        """Enter the async connection context."""

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> bool | None:
        """Exit the async connection context."""


class DatabaseConnectable(Protocol):
    """Minimal engine contract used by the health probe."""

    def connect(self) -> DatabaseConnectionContext:
        """Open an async connection context."""


@dataclass(frozen=True)
class DatabaseHealthResult:
    """Safe database health result without credentials."""

    ok: bool
    error_type: str | None = None


async def check_database_connection(engine: DatabaseConnectable) -> DatabaseHealthResult:
    """Run a read-only PostgreSQL connectivity probe."""

    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            return DatabaseHealthResult(ok=result.scalar_one() == 1)
    except Exception as exc:  # noqa: BLE001
        return DatabaseHealthResult(ok=False, error_type=type(exc).__name__)
