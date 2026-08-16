"""Live PostgreSQL integration tests for KaitenConnectionService."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kvc_application.dto import (
    BindKaitenConnectionInput,
    EncryptedToken,
    KaitenCredentialVerification,
    MarkKaitenNeedsReauthInput,
)
from kvc_application.errors import (
    CredentialDecryptionFailed,
    CredentialEncryptionFailed,
    KaitenAuthenticationFailed,
    KaitenConnectionDisabled,
    KaitenConnectionMissing,
    KaitenConnectionNeedsReauth,
    KaitenTemporarilyUnavailable,
    KaitenVerificationFailed,
    PersistenceConflict,
    UserDisabled,
)
from kvc_application.services import KaitenConnectionService
from kvc_config import get_settings
from kvc_integrations.security import VersionedFernetTokenCipher
from kvc_persistence import (
    create_async_engine_from_settings,
    create_async_sessionmaker,
    dispose_async_engine,
)
from kvc_persistence.models import (
    DialogSession,
    KaitenConnection,
    MaxChat,
    NotificationHistory,
    NotificationSetting,
    PendingCommand,
    User,
)
from kvc_persistence.repositories import KaitenConnectionRepository, UserRepository

EXPECTED_REVISION = "00201_mvp_service_model"
BUSINESS_TABLES = (
    "dialog_sessions",
    "kaiten_connections",
    "max_chats",
    "notification_history",
    "notification_settings",
    "pending_commands",
    "users",
)
TOKEN_A = "synthetic-token-a"
TOKEN_B = "synthetic-token-b"


@pytest_asyncio.fixture
async def live_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    if settings.app_env != "development":
        pytest.skip("KaitenConnectionService integration tests require KVC_APP_ENV=development.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip(
                    "KaitenConnectionService integration tests require the kvc_dev database."
                )

            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip(
                    "KaitenConnectionService integration tests require accepted Alembic head."
                )

        yield engine
    finally:
        await dispose_async_engine(engine)


async def table_counts(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as conn:
        counts = {}
        for table_name in BUSINESS_TABLES:
            counts[table_name] = (
                await conn.execute(text(f"SELECT count(*) FROM {table_name}"))
            ).scalar_one()
        return counts


class FakeVerifier:
    def __init__(
        self,
        verification: KaitenCredentialVerification | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._verification = verification or KaitenCredentialVerification(
            kaiten_user_id="synthetic-kaiten-user",
            workspace_id=None,
        )
        self._exc = exc
        self.calls = 0

    async def verify(
        self,
        *,
        api_base_url: str,
        plaintext_token: str,
    ) -> KaitenCredentialVerification:
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return self._verification


class FailingCipher:
    def encrypt(self, plaintext: str) -> EncryptedToken:
        raise CredentialEncryptionFailed("synthetic encryption failure")

    def decrypt(self, ciphertext: bytes, version: int) -> str:
        raise AssertionError("decrypt must not be called")


class FailingDecryptCipher:
    def encrypt(self, plaintext: str) -> EncryptedToken:
        raise AssertionError("encrypt must not be called")

    def decrypt(self, ciphertext: bytes, version: int) -> str:
        raise CredentialDecryptionFailed("synthetic decryption failure")


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


@dataclass
class ConnectionContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    baseline_counts: dict[str, int]
    user_ids: list[uuid.UUID]

    def cipher(self) -> VersionedFernetTokenCipher:
        key = Fernet.generate_key().decode("ascii")
        return VersionedFernetTokenCipher(keys={1: key}, active_version=1)

    def service(
        self,
        *,
        verifier: FakeVerifier | None = None,
        cipher: VersionedFernetTokenCipher | FailingCipher | None = None,
        now: datetime | None = None,
    ) -> KaitenConnectionService:
        return KaitenConnectionService(
            self.sessionmaker,
            verifier or FakeVerifier(),
            cipher or self.cipher(),
            FixedClock(now or datetime(2026, 8, 16, 12, tzinfo=UTC)),
        )

    def input(
        self,
        user_id: uuid.UUID,
        *,
        token: str = TOKEN_A,
        api_base_url: str = "https://synthetic.kaiten.example/api/latest",
    ) -> BindKaitenConnectionInput:
        return BindKaitenConnectionInput(
            user_id=user_id,
            api_base_url=api_base_url,
            plaintext_token=token,
        )


@pytest_asyncio.fixture
async def connection_context(live_engine: AsyncEngine) -> AsyncIterator[ConnectionContext]:
    context = ConnectionContext(
        engine=live_engine,
        sessionmaker=create_async_sessionmaker(live_engine),
        baseline_counts=await table_counts(live_engine),
        user_ids=[],
    )
    try:
        yield context
    finally:
        await cleanup_users(live_engine, context.user_ids)
        assert await table_counts(live_engine) == context.baseline_counts


async def cleanup_users(engine: AsyncEngine, user_ids: list[uuid.UUID]) -> None:
    if not user_ids:
        return
    async with engine.begin() as conn:
        await conn.execute(
            delete(NotificationHistory).where(NotificationHistory.user_id.in_(user_ids))
        )
        await conn.execute(delete(PendingCommand).where(PendingCommand.user_id.in_(user_ids)))
        await conn.execute(delete(DialogSession).where(DialogSession.user_id.in_(user_ids)))
        await conn.execute(
            delete(NotificationSetting).where(NotificationSetting.user_id.in_(user_ids))
        )
        await conn.execute(delete(KaitenConnection).where(KaitenConnection.user_id.in_(user_ids)))
        await conn.execute(delete(MaxChat).where(MaxChat.user_id.in_(user_ids)))
        await conn.execute(delete(User).where(User.id.in_(user_ids)))


async def create_user(context: ConnectionContext, *, status: str = "ACTIVE") -> uuid.UUID:
    async with context.sessionmaker() as session:
        async with session.begin():
            user = await UserRepository(session).create(status=status)
            context.user_ids.append(user.id)
            return user.id


async def load_connection(context: ConnectionContext, user_id: uuid.UUID) -> KaitenConnection:
    async with context.sessionmaker() as session:
        connection = await KaitenConnectionRepository(session).get_for_user(user_id)
        assert connection is not None
        return connection


async def count_connections(context: ConnectionContext, user_id: uuid.UUID) -> int:
    async with context.sessionmaker() as session:
        connections = (
            (
                await session.execute(
                    select(KaitenConnection).where(KaitenConnection.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        return len(connections)


async def set_user_status(context: ConnectionContext, user_id: uuid.UUID, status: str) -> None:
    async with context.sessionmaker() as session:
        async with session.begin():
            user = await UserRepository(session).get_by_id_for_update(user_id)
            assert user is not None
            await UserRepository(session).set_status(user, status)


async def set_connection_status(
    context: ConnectionContext,
    user_id: uuid.UUID,
    status: str,
) -> None:
    async with context.sessionmaker() as session:
        async with session.begin():
            connection = await KaitenConnectionRepository(session).get_for_user_for_update(user_id)
            assert connection is not None
            connection.status = status
            await session.flush()


def snapshot(connection: KaitenConnection) -> tuple[object, ...]:
    return (
        connection.id,
        connection.user_id,
        connection.api_base_url,
        connection.kaiten_user_id,
        connection.workspace_id,
        bytes(connection.encrypted_api_token),
        connection.token_encryption_version,
        connection.status,
        connection.last_verified_at,
    )


@pytest.mark.asyncio
async def test_first_bind_creates_active_encrypted_connection(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    cipher = connection_context.cipher()
    fixed_now = datetime(2026, 8, 16, 12, tzinfo=UTC)
    verifier = FakeVerifier(KaitenCredentialVerification("synthetic-kaiten-user-1", None))
    service = connection_context.service(verifier=verifier, cipher=cipher, now=fixed_now)

    result = await service.bind_or_replace_connection(
        connection_context.input(user_id, token=TOKEN_A)
    )
    connection = await load_connection(connection_context, user_id)

    assert result.status == "ACTIVE"
    assert result.connection_id == connection.id
    assert result.user_id == user_id
    assert result.kaiten_user_id == "synthetic-kaiten-user-1"
    assert result.workspace_id is None
    assert result.last_verified_at == fixed_now
    assert connection.api_base_url == "https://synthetic.kaiten.example/api/latest"
    assert connection.status == "ACTIVE"
    assert connection.encrypted_api_token != TOKEN_A.encode("utf-8")
    assert connection.token_encryption_version == 1
    assert connection.last_verified_at == fixed_now
    assert (
        cipher.decrypt(bytes(connection.encrypted_api_token), connection.token_encryption_version)
        == TOKEN_A
    )
    assert TOKEN_A not in repr(result)
    assert bytes(connection.encrypted_api_token).decode("ascii") not in repr(result)
    assert verifier.calls == 1


@pytest.mark.asyncio
async def test_replacement_reuses_row_and_updates_credential_fields(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    cipher = connection_context.cipher()
    service_a = connection_context.service(
        verifier=FakeVerifier(KaitenCredentialVerification("kaiten-a", "workspace-a")),
        cipher=cipher,
        now=datetime(2026, 8, 16, 12, tzinfo=UTC),
    )
    await service_a.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    first = await load_connection(connection_context, user_id)
    first_snapshot = snapshot(first)

    service_b = connection_context.service(
        verifier=FakeVerifier(KaitenCredentialVerification("kaiten-b", None)),
        cipher=cipher,
        now=datetime(2026, 8, 16, 13, tzinfo=UTC),
    )
    result = await service_b.bind_or_replace_connection(
        connection_context.input(
            user_id,
            token=TOKEN_B,
            api_base_url="https://synthetic.kaiten.example/api/v1",
        )
    )
    second = await load_connection(connection_context, user_id)

    assert result.connection_id == first_snapshot[0]
    assert second.id == first_snapshot[0]
    assert await count_connections(connection_context, user_id) == 1
    assert second.status == "ACTIVE"
    assert second.api_base_url == "https://synthetic.kaiten.example/api/v1"
    assert second.kaiten_user_id == "kaiten-b"
    assert second.workspace_id is None
    assert bytes(second.encrypted_api_token) != first_snapshot[5]
    assert (
        cipher.decrypt(bytes(second.encrypted_api_token), second.token_encryption_version)
        == TOKEN_B
    )
    assert second.last_verified_at == datetime(2026, 8, 16, 13, tzinfo=UTC)


@pytest.mark.parametrize("initial_status", ["NEEDS_REAUTH", "DISABLED"])
@pytest.mark.asyncio
async def test_successful_rebind_reenables_existing_connection(
    connection_context: ConnectionContext,
    initial_status: str,
) -> None:
    user_id = await create_user(connection_context)
    cipher = connection_context.cipher()
    verifier = FakeVerifier()
    service = connection_context.service(verifier=verifier, cipher=cipher)
    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    await set_connection_status(connection_context, user_id, initial_status)

    result = await service.bind_or_replace_connection(
        connection_context.input(user_id, token=TOKEN_B)
    )
    connection = await load_connection(connection_context, user_id)

    assert result.status == "ACTIVE"
    assert connection.status == "ACTIVE"
    assert (
        cipher.decrypt(bytes(connection.encrypted_api_token), connection.token_encryption_version)
        == TOKEN_B
    )


@pytest.mark.asyncio
async def test_disabled_kvc_user_cannot_bind_and_connection_is_unchanged(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    service = connection_context.service()
    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    before = snapshot(await load_connection(connection_context, user_id))
    await set_user_status(connection_context, user_id, "DISABLED")

    with pytest.raises(UserDisabled):
        await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_B))

    assert snapshot(await load_connection(connection_context, user_id)) == before


@pytest.mark.asyncio
async def test_user_disabled_during_verification_is_rechecked_before_write(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)

    class DisablingVerifier(FakeVerifier):
        async def verify(
            self,
            *,
            api_base_url: str,
            plaintext_token: str,
        ) -> KaitenCredentialVerification:
            await set_user_status(connection_context, user_id, "DISABLED")
            return await super().verify(api_base_url=api_base_url, plaintext_token=plaintext_token)

    service = connection_context.service(verifier=DisablingVerifier())

    with pytest.raises(UserDisabled):
        await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))

    async with connection_context.sessionmaker() as session:
        assert await KaitenConnectionRepository(session).get_for_user(user_id) is None


@pytest.mark.parametrize(
    "error",
    [
        KaitenAuthenticationFailed("synthetic auth failure"),
        KaitenTemporarilyUnavailable("synthetic temporary failure"),
        KaitenVerificationFailed("synthetic contract failure"),
    ],
)
@pytest.mark.asyncio
async def test_verifier_failure_preserves_existing_connection(
    connection_context: ConnectionContext,
    error: Exception,
) -> None:
    user_id = await create_user(connection_context)
    service = connection_context.service()
    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    before = snapshot(await load_connection(connection_context, user_id))
    failing = connection_context.service(verifier=FakeVerifier(exc=error))

    with pytest.raises(type(error)):
        await failing.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_B))

    assert snapshot(await load_connection(connection_context, user_id)) == before


@pytest.mark.asyncio
async def test_encryption_failure_preserves_existing_connection(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    service = connection_context.service()
    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    before = snapshot(await load_connection(connection_context, user_id))
    failing = connection_context.service(cipher=FailingCipher())

    with pytest.raises(CredentialEncryptionFailed):
        await failing.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_B))

    assert snapshot(await load_connection(connection_context, user_id)) == before


@pytest.mark.asyncio
async def test_get_active_connection_secret_returns_plaintext_and_exact_snapshot(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    cipher = connection_context.cipher()
    verifier = FakeVerifier()
    service = connection_context.service(verifier=verifier, cipher=cipher)
    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    connection = await load_connection(connection_context, user_id)

    secret = await service.get_active_connection_secret(user_id)

    assert secret.plaintext_token == TOKEN_A
    assert secret.snapshot.connection_id == connection.id
    assert secret.snapshot.encrypted_api_token == bytes(connection.encrypted_api_token)
    assert secret.snapshot.token_encryption_version == connection.token_encryption_version
    assert TOKEN_A not in repr(secret)
    assert bytes(connection.encrypted_api_token).decode("ascii") not in repr(secret)
    assert verifier.calls == 1


@pytest.mark.asyncio
async def test_get_active_connection_secret_decrypt_failure_propagates(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    await connection_context.service().bind_or_replace_connection(
        connection_context.input(user_id, token=TOKEN_A)
    )
    failing_service = connection_context.service(cipher=FailingDecryptCipher())

    with pytest.raises(CredentialDecryptionFailed):
        await failing_service.get_active_connection_secret(user_id)


@pytest.mark.parametrize(
    ("user_status", "connection_status", "expected_error"),
    [
        ("DISABLED", "ACTIVE", UserDisabled),
        ("ACTIVE", "DISABLED", KaitenConnectionDisabled),
        ("ACTIVE", "NEEDS_REAUTH", KaitenConnectionNeedsReauth),
    ],
)
@pytest.mark.asyncio
async def test_get_active_connection_secret_state_errors(
    connection_context: ConnectionContext,
    user_status: str,
    connection_status: str,
    expected_error: type[Exception],
) -> None:
    user_id = await create_user(connection_context)
    service = connection_context.service()
    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    await set_user_status(connection_context, user_id, user_status)
    await set_connection_status(connection_context, user_id, connection_status)

    with pytest.raises(expected_error):
        await service.get_active_connection_secret(user_id)


@pytest.mark.asyncio
async def test_get_active_connection_secret_missing_connection(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)

    with pytest.raises(KaitenConnectionMissing):
        await connection_context.service().get_active_connection_secret(user_id)


@pytest.mark.asyncio
async def test_missing_user_operations_are_controlled_errors(
    connection_context: ConnectionContext,
) -> None:
    missing_user_id = uuid.uuid4()
    service = connection_context.service()

    with pytest.raises(PersistenceConflict):
        await service.bind_or_replace_connection(connection_context.input(missing_user_id))
    with pytest.raises(PersistenceConflict):
        await service.disable_connection(missing_user_id)
    with pytest.raises(PersistenceConflict):
        await service.get_active_connection_secret(missing_user_id)


@pytest.mark.asyncio
async def test_mark_needs_reauth_stale_snapshot_after_replacement_is_noop(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    cipher = connection_context.cipher()
    service = connection_context.service(cipher=cipher)
    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    old_secret = await service.get_active_connection_secret(user_id)

    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_B))
    current = await load_connection(connection_context, user_id)
    assert current.id == old_secret.snapshot.connection_id
    assert current.token_encryption_version == old_secret.snapshot.token_encryption_version
    assert bytes(current.encrypted_api_token) != old_secret.snapshot.encrypted_api_token

    result = await service.mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=user_id,
            snapshot=old_secret.snapshot,
            reason="authentication_failed",
        )
    )
    after = await load_connection(connection_context, user_id)

    assert result is None
    assert after.status == "ACTIVE"
    assert (
        cipher.decrypt(bytes(after.encrypted_api_token), after.token_encryption_version) == TOKEN_B
    )


@pytest.mark.asyncio
async def test_mark_needs_reauth_current_snapshot_is_idempotent(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    service = connection_context.service(now=datetime(2026, 8, 16, 12, tzinfo=UTC))
    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    secret = await service.get_active_connection_secret(user_id)
    before = await load_connection(connection_context, user_id)
    before_verified_at = before.last_verified_at
    before_ciphertext = bytes(before.encrypted_api_token)

    first = await service.mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=user_id,
            snapshot=secret.snapshot,
            reason="authentication_failed",
        )
    )
    second = await service.mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=user_id,
            snapshot=secret.snapshot,
            reason="authentication_failed",
        )
    )
    after = await load_connection(connection_context, user_id)

    assert first is not None
    assert second is not None
    assert first.status == "NEEDS_REAUTH"
    assert second.status == "NEEDS_REAUTH"
    assert after.status == "NEEDS_REAUTH"
    assert bytes(after.encrypted_api_token) == before_ciphertext
    assert after.last_verified_at == before_verified_at


@pytest.mark.asyncio
async def test_mark_needs_reauth_matching_disabled_snapshot_remains_disabled(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    service = connection_context.service()
    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    secret = await service.get_active_connection_secret(user_id)
    await set_connection_status(connection_context, user_id, "DISABLED")

    result = await service.mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=user_id,
            snapshot=secret.snapshot,
            reason="authentication_failed",
        )
    )

    assert result is not None
    assert result.status == "DISABLED"
    assert (await load_connection(connection_context, user_id)).status == "DISABLED"


@pytest.mark.asyncio
async def test_mark_needs_reauth_missing_connection_returns_none(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)

    result = await connection_context.service().mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=user_id,
            snapshot=object(),  # type: ignore[arg-type]
            reason="authentication_failed",
        )
    )

    assert result is None


@pytest.mark.asyncio
async def test_disable_lifecycle_retains_credential_fields(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    service = connection_context.service(now=datetime(2026, 8, 16, 12, tzinfo=UTC))
    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    before = await load_connection(connection_context, user_id)
    before_ciphertext = bytes(before.encrypted_api_token)

    first = await service.disable_connection(user_id)
    second = await service.disable_connection(user_id)
    after = await load_connection(connection_context, user_id)

    assert first.status == "DISABLED"
    assert second.status == "DISABLED"
    assert after.status == "DISABLED"
    assert bytes(after.encrypted_api_token) == before_ciphertext
    assert after.token_encryption_version == before.token_encryption_version
    assert after.last_verified_at == before.last_verified_at

    with pytest.raises(KaitenConnectionDisabled):
        await service.get_active_connection_secret(user_id)


@pytest.mark.asyncio
async def test_disable_from_needs_reauth_and_disabled_kvc_user_is_allowed(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    service = connection_context.service()
    await service.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    await set_connection_status(connection_context, user_id, "NEEDS_REAUTH")
    await set_user_status(connection_context, user_id, "DISABLED")

    result = await service.disable_connection(user_id)

    assert result.status == "DISABLED"
    assert (await load_connection(connection_context, user_id)).status == "DISABLED"


@pytest.mark.asyncio
async def test_disable_missing_connection_raises(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)

    with pytest.raises(KaitenConnectionMissing):
        await connection_context.service().disable_connection(user_id)


@pytest.mark.asyncio
async def test_sequential_verified_replacements_leave_one_last_writer_row(
    connection_context: ConnectionContext,
) -> None:
    user_id = await create_user(connection_context)
    cipher = connection_context.cipher()
    first = connection_context.service(
        verifier=FakeVerifier(KaitenCredentialVerification("first", None)),
        cipher=cipher,
        now=datetime(2026, 8, 16, 12, tzinfo=UTC),
    )
    second = connection_context.service(
        verifier=FakeVerifier(KaitenCredentialVerification("second", None)),
        cipher=cipher,
        now=datetime(2026, 8, 16, 12, 1, tzinfo=UTC),
    )

    await first.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_A))
    await second.bind_or_replace_connection(connection_context.input(user_id, token=TOKEN_B))
    connection = await load_connection(connection_context, user_id)

    assert await count_connections(connection_context, user_id) == 1
    assert connection.kaiten_user_id == "second"
    assert (
        cipher.decrypt(bytes(connection.encrypted_api_token), connection.token_encryption_version)
        == TOKEN_B
    )
    assert connection.last_verified_at == datetime(2026, 8, 16, 12, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_kaiten_connection_service_integration_database_returns_to_baseline(
    connection_context: ConnectionContext,
) -> None:
    assert await table_counts(connection_context.engine) == connection_context.baseline_counts
