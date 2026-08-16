"""Full application-service acceptance over live PostgreSQL."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import FrozenInstanceError, dataclass
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kvc_application import (
    BindKaitenConnectionInput,
    IdentityConflict,
    IdentityService,
    KaitenConnectionService,
    KaitenCredentialSnapshot,
    KaitenCredentialVerification,
    MarkKaitenNeedsReauthInput,
    ResolveMaxIdentityInput,
)
from kvc_application.errors import (
    CredentialDecryptionFailed,
    CredentialEncryptionFailed,
    KaitenAuthenticationFailed,
    KaitenTemporarilyUnavailable,
    KaitenVerificationFailed,
    UserDisabled,
)
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
from kvc_persistence.repositories import (
    KaitenConnectionRepository,
    MaxChatRepository,
    NotificationSettingsRepository,
    UserRepository,
)

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


class FakeVerifier:
    def __init__(
        self,
        *,
        kaiten_user_id: str = "synthetic-kaiten-user",
        workspace_id: str | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._verification = KaitenCredentialVerification(kaiten_user_id, workspace_id)
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


class FailingEncryptCipher:
    def encrypt(self, plaintext: str) -> object:
        raise CredentialEncryptionFailed("synthetic encryption failure")

    def decrypt(self, ciphertext: bytes, version: int) -> str:
        raise AssertionError("decrypt must not be called")


class FixedClock:
    def __init__(self, *values: datetime) -> None:
        self._values = list(values)
        self._last_value = values[-1] if values else None
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        if self._values:
            self._last_value = self._values.pop(0)
            return self._last_value
        if self._last_value is None:
            raise AssertionError("test clock exhausted")
        return self._last_value


@dataclass
class AcceptanceContext:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker
    prefix: str
    baseline_counts: dict[str, int]
    user_ids: list[uuid.UUID]

    def identity_input(self, user_label: str, chat_label: str) -> ResolveMaxIdentityInput:
        return ResolveMaxIdentityInput(
            max_user_id=f"{self.prefix}-max-user-{user_label}",
            max_chat_id=f"{self.prefix}-max-chat-{chat_label}",
            chat_type="PRIVATE",
        )

    def bind_input(
        self,
        user_id: uuid.UUID,
        token_label: str,
        *,
        api_base_url: str = "https://synthetic.kaiten.example/api/latest",
    ) -> BindKaitenConnectionInput:
        return BindKaitenConnectionInput(
            user_id=user_id,
            api_base_url=api_base_url,
            plaintext_token=f"{self.prefix}-token-{token_label}",
        )

    def cipher(
        self,
        *,
        keys: dict[int, str] | None = None,
        active_version: int = 1,
    ) -> VersionedFernetTokenCipher:
        return VersionedFernetTokenCipher(
            keys=keys or {active_version: Fernet.generate_key().decode("ascii")},
            active_version=active_version,
        )

    def connection_service(
        self,
        *,
        verifier: FakeVerifier | None = None,
        cipher: object | None = None,
        clock: FixedClock | None = None,
    ) -> KaitenConnectionService:
        return KaitenConnectionService(
            self.sessionmaker,
            verifier or FakeVerifier(),
            cipher or self.cipher(),
            clock or FixedClock(datetime(2026, 8, 16, 12, tzinfo=UTC)),
        )


@pytest_asyncio.fixture
async def live_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    if settings.app_env != "development":
        pytest.skip("Application-service acceptance requires KVC_APP_ENV=development.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip("Application-service acceptance requires the kvc_dev database.")

            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip("Application-service acceptance requires accepted Alembic head.")

        yield engine
    finally:
        await dispose_async_engine(engine)


@pytest_asyncio.fixture
async def acceptance_context(live_engine: AsyncEngine) -> AsyncIterator[AcceptanceContext]:
    context = AcceptanceContext(
        engine=live_engine,
        sessionmaker=create_async_sessionmaker(live_engine),
        prefix=f"synthetic-acceptance-{uuid.uuid4()}",
        baseline_counts=await table_counts(live_engine),
        user_ids=[],
    )
    try:
        yield context
    finally:
        await cleanup_users(live_engine, context.user_ids)
        assert await table_counts(live_engine) == context.baseline_counts


async def table_counts(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as conn:
        counts = {}
        for table_name in BUSINESS_TABLES:
            counts[table_name] = (
                await conn.execute(text(f"SELECT count(*) FROM {table_name}"))
            ).scalar_one()
        return counts


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


async def record_user(context: AcceptanceContext, user_id: uuid.UUID) -> uuid.UUID:
    if user_id not in context.user_ids:
        context.user_ids.append(user_id)
    return user_id


async def create_user(context: AcceptanceContext, *, status: str = "ACTIVE") -> uuid.UUID:
    async with context.sessionmaker() as session:
        async with session.begin():
            user = await UserRepository(session).create(status=status)
            return await record_user(context, user.id)


async def load_connection(context: AcceptanceContext, user_id: uuid.UUID) -> KaitenConnection:
    async with context.sessionmaker() as session:
        connection = await KaitenConnectionRepository(session).get_for_user(user_id)
        assert connection is not None
        return connection


async def load_binding(context: AcceptanceContext, max_user_id: str) -> MaxChat:
    async with context.sessionmaker() as session:
        binding = await MaxChatRepository(session).get_private_by_max_user_id(max_user_id)
        assert binding is not None
        return binding


async def load_settings(context: AcceptanceContext, user_id: uuid.UUID) -> NotificationSetting:
    async with context.sessionmaker() as session:
        settings = await NotificationSettingsRepository(session).get_for_user(user_id)
        assert settings is not None
        return settings


async def set_user_status(context: AcceptanceContext, user_id: uuid.UUID, status: str) -> None:
    async with context.sessionmaker() as session:
        async with session.begin():
            user = await UserRepository(session).get_by_id_for_update(user_id)
            assert user is not None
            await UserRepository(session).set_status(user, status)


async def set_connection_ciphertext_and_version(
    context: AcceptanceContext,
    user_id: uuid.UUID,
    *,
    ciphertext: bytes,
    version: int,
) -> None:
    async with context.sessionmaker() as session:
        async with session.begin():
            connection = await KaitenConnectionRepository(session).get_for_user_for_update(user_id)
            assert connection is not None
            connection.encrypted_api_token = ciphertext
            connection.token_encryption_version = version
            await session.flush()


async def connection_count(context: AcceptanceContext, user_id: uuid.UUID) -> int:
    async with context.sessionmaker() as session:
        rows = (
            (
                await session.execute(
                    select(KaitenConnection).where(KaitenConnection.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        return len(rows)


async def settings_count(context: AcceptanceContext, user_id: uuid.UUID) -> int:
    async with context.sessionmaker() as session:
        rows = (
            (
                await session.execute(
                    select(NotificationSetting).where(NotificationSetting.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        return len(rows)


def connection_snapshot(connection: KaitenConnection) -> tuple[object, ...]:
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
async def test_full_application_lifecycle_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    identity_service = IdentityService(acceptance_context.sessionmaker)
    cipher = acceptance_context.cipher()
    clock = FixedClock(
        datetime(2026, 8, 16, 10, tzinfo=UTC),
        datetime(2026, 8, 16, 11, tzinfo=UTC),
        datetime(2026, 8, 16, 12, tzinfo=UTC),
    )
    connection_service = acceptance_context.connection_service(cipher=cipher, clock=clock)

    identity = await identity_service.resolve_or_onboard_private_max_user(
        acceptance_context.identity_input("u1", "c1")
    )
    await record_user(acceptance_context, identity.user_id)
    settings = await load_settings(acceptance_context, identity.user_id)

    assert identity.is_new_user is True
    assert identity.user_status == "ACTIVE"
    assert settings.enabled is False
    assert settings.due_soon_days == 1
    assert settings.timezone == "UTC"

    bind_a = await connection_service.bind_or_replace_connection(
        acceptance_context.bind_input(identity.user_id, "a")
    )
    secret_a = await connection_service.get_active_connection_secret(identity.user_id)
    mark_a = await connection_service.mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=identity.user_id,
            snapshot=secret_a.snapshot,
            reason="authentication_failed",
        )
    )
    bind_b = await connection_service.bind_or_replace_connection(
        acceptance_context.bind_input(identity.user_id, "b")
    )
    secret_b = await connection_service.get_active_connection_secret(identity.user_id)
    disabled = await connection_service.disable_connection(identity.user_id)
    bind_c = await connection_service.bind_or_replace_connection(
        acceptance_context.bind_input(identity.user_id, "c")
    )
    final_secret = await connection_service.get_active_connection_secret(identity.user_id)

    assert bind_a.status == "ACTIVE"
    assert secret_a.plaintext_token.endswith("-token-a")
    assert mark_a is not None
    assert mark_a.status == "NEEDS_REAUTH"
    assert bind_b.connection_id == bind_a.connection_id
    assert bind_b.status == "ACTIVE"
    assert secret_b.plaintext_token.endswith("-token-b")
    assert secret_b.snapshot.connection_id == bind_a.connection_id
    assert disabled.status == "DISABLED"
    assert bind_c.connection_id == bind_a.connection_id
    assert bind_c.status == "ACTIVE"
    assert final_secret.plaintext_token.endswith("-token-c")
    assert await connection_count(acceptance_context, identity.user_id) == 1


@pytest.mark.asyncio
async def test_cross_user_isolation_and_identity_rotation_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    identity_service = IdentityService(acceptance_context.sessionmaker)
    cipher = acceptance_context.cipher()
    service = acceptance_context.connection_service(cipher=cipher)

    first = await identity_service.resolve_or_onboard_private_max_user(
        acceptance_context.identity_input("u1", "c1")
    )
    second = await identity_service.resolve_or_onboard_private_max_user(
        acceptance_context.identity_input("u2", "c2")
    )
    await record_user(acceptance_context, first.user_id)
    await record_user(acceptance_context, second.user_id)
    await service.bind_or_replace_connection(acceptance_context.bind_input(first.user_id, "a"))
    await service.bind_or_replace_connection(acceptance_context.bind_input(second.user_id, "b"))
    first_before = connection_snapshot(await load_connection(acceptance_context, first.user_id))
    second_before = connection_snapshot(await load_connection(acceptance_context, second.user_id))

    rotated = await identity_service.resolve_or_onboard_private_max_user(
        acceptance_context.identity_input("u1", "c1-rotated")
    )
    await service.disable_connection(first.user_id)
    first_secret_before_disable = await service.mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=second.user_id,
            snapshot=KaitenCredentialSnapshot(
                connection_id=uuid.uuid4(),
                encrypted_api_token=b"stale-other-user",
                token_encryption_version=1,
            ),
            reason="authentication_failed",
        )
    )
    first_after = await load_connection(acceptance_context, first.user_id)
    second_after = await load_connection(acceptance_context, second.user_id)

    assert rotated.user_id == first.user_id
    assert rotated.max_chat_binding_id == first.max_chat_binding_id
    assert rotated.kaiten_connection_status == "ACTIVE"
    assert first_after.id == first_before[0]
    assert first_after.status == "DISABLED"
    assert bytes(first_after.encrypted_api_token) == first_before[5]
    assert first_secret_before_disable is None
    assert connection_snapshot(second_after) == second_before


@pytest.mark.asyncio
async def test_disabled_user_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    identity_service = IdentityService(acceptance_context.sessionmaker)
    identity = await identity_service.resolve_or_onboard_private_max_user(
        acceptance_context.identity_input("u1", "c1")
    )
    await record_user(acceptance_context, identity.user_id)
    service = acceptance_context.connection_service()
    await service.bind_or_replace_connection(acceptance_context.bind_input(identity.user_id, "a"))
    await set_user_status(acceptance_context, identity.user_id, "DISABLED")

    resolved = await identity_service.resolve_or_onboard_private_max_user(
        acceptance_context.identity_input("u1", "c1")
    )

    assert resolved.user_status == "DISABLED"
    with pytest.raises(UserDisabled):
        await service.bind_or_replace_connection(
            acceptance_context.bind_input(identity.user_id, "b")
        )
    with pytest.raises(UserDisabled):
        await service.get_active_connection_secret(identity.user_id)
    disabled = await service.disable_connection(identity.user_id)
    repeated = await service.disable_connection(identity.user_id)
    assert disabled.status == "DISABLED"
    assert repeated.status == "DISABLED"


@pytest.mark.asyncio
async def test_notification_defaults_and_identity_idempotency_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    identity_service = IdentityService(acceptance_context.sessionmaker)
    input = acceptance_context.identity_input("u1", "c1")
    first = await identity_service.resolve_or_onboard_private_max_user(input)
    await record_user(acceptance_context, first.user_id)
    settings = await load_settings(acceptance_context, first.user_id)
    settings_snapshot = (settings.enabled, settings.due_soon_days, settings.timezone)

    repeated = await identity_service.resolve_or_onboard_private_max_user(input)
    rotated = await identity_service.resolve_or_onboard_private_max_user(
        acceptance_context.identity_input("u1", "c2")
    )

    assert repeated.user_id == first.user_id
    assert rotated.user_id == first.user_id
    assert await settings_count(acceptance_context, first.user_id) == 1
    after = await load_settings(acceptance_context, first.user_id)
    assert (after.enabled, after.due_soon_days, after.timezone) == settings_snapshot


@pytest.mark.asyncio
async def test_max_rotation_preserves_kaiten_connection_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    identity_service = IdentityService(acceptance_context.sessionmaker)
    first = await identity_service.resolve_or_onboard_private_max_user(
        acceptance_context.identity_input("u1", "c1")
    )
    await record_user(acceptance_context, first.user_id)
    service = acceptance_context.connection_service()
    await service.bind_or_replace_connection(acceptance_context.bind_input(first.user_id, "a"))
    before = connection_snapshot(await load_connection(acceptance_context, first.user_id))

    rotated = await identity_service.resolve_or_onboard_private_max_user(
        acceptance_context.identity_input("u1", "c2")
    )
    binding = await load_binding(
        acceptance_context, acceptance_context.identity_input("u1", "c1").max_user_id
    )
    after = connection_snapshot(await load_connection(acceptance_context, first.user_id))

    assert rotated.user_id == first.user_id
    assert rotated.max_chat_binding_id == first.max_chat_binding_id
    assert binding.id == first.max_chat_binding_id
    assert binding.max_chat_id == acceptance_context.identity_input("u1", "c2").max_chat_id
    assert after == before


@pytest.mark.asyncio
async def test_identity_conflict_preserves_connections_and_settings_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    identity_service = IdentityService(acceptance_context.sessionmaker)
    cipher = acceptance_context.cipher()
    service = acceptance_context.connection_service(cipher=cipher)
    first_input = acceptance_context.identity_input("u1", "c1")
    second_input = acceptance_context.identity_input("u2", "c2")
    first = await identity_service.resolve_or_onboard_private_max_user(first_input)
    second = await identity_service.resolve_or_onboard_private_max_user(second_input)
    await record_user(acceptance_context, first.user_id)
    await record_user(acceptance_context, second.user_id)
    await service.bind_or_replace_connection(acceptance_context.bind_input(first.user_id, "a"))
    await service.bind_or_replace_connection(acceptance_context.bind_input(second.user_id, "b"))
    before = {
        first.user_id: connection_snapshot(
            await load_connection(acceptance_context, first.user_id)
        ),
        second.user_id: connection_snapshot(
            await load_connection(acceptance_context, second.user_id)
        ),
    }
    first_settings = await settings_count(acceptance_context, first.user_id)
    second_settings = await settings_count(acceptance_context, second.user_id)

    with pytest.raises(IdentityConflict):
        await identity_service.resolve_or_onboard_private_max_user(
            ResolveMaxIdentityInput(
                max_user_id=first_input.max_user_id,
                max_chat_id=second_input.max_chat_id,
                chat_type="PRIVATE",
            )
        )

    assert (
        connection_snapshot(await load_connection(acceptance_context, first.user_id))
        == before[first.user_id]
    )
    assert (
        connection_snapshot(await load_connection(acceptance_context, second.user_id))
        == before[second.user_id]
    )
    assert await settings_count(acceptance_context, first.user_id) == first_settings
    assert await settings_count(acceptance_context, second.user_id) == second_settings


@pytest.mark.parametrize(
    "failure",
    [
        KaitenAuthenticationFailed("synthetic auth failure"),
        KaitenTemporarilyUnavailable("synthetic temporary failure"),
        KaitenVerificationFailed("synthetic verification failure"),
        CredentialEncryptionFailed("synthetic encryption failure"),
    ],
)
@pytest.mark.asyncio
async def test_verify_before_persist_failures_preserve_row_acceptance(
    acceptance_context: AcceptanceContext,
    failure: Exception,
) -> None:
    user_id = await create_user(acceptance_context)
    service = acceptance_context.connection_service()
    await service.bind_or_replace_connection(acceptance_context.bind_input(user_id, "a"))
    before = connection_snapshot(await load_connection(acceptance_context, user_id))
    if isinstance(failure, CredentialEncryptionFailed):
        failing_service = acceptance_context.connection_service(cipher=FailingEncryptCipher())
    else:
        failing_service = acceptance_context.connection_service(verifier=FakeVerifier(exc=failure))

    with pytest.raises(type(failure)):
        await failing_service.bind_or_replace_connection(
            acceptance_context.bind_input(user_id, "b")
        )

    assert connection_snapshot(await load_connection(acceptance_context, user_id)) == before


@pytest.mark.asyncio
async def test_last_verified_at_and_snapshot_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    user_id = await create_user(acceptance_context)
    t1 = datetime(2026, 8, 16, 10, tzinfo=UTC)
    t2 = datetime(2026, 8, 16, 11, tzinfo=UTC)
    cipher = acceptance_context.cipher()
    service = acceptance_context.connection_service(cipher=cipher, clock=FixedClock(t1, t2))
    await service.bind_or_replace_connection(acceptance_context.bind_input(user_id, "a"))
    first = await load_connection(acceptance_context, user_id)
    assert first.last_verified_at == t1

    secret_a = await service.get_active_connection_secret(user_id)
    await service.bind_or_replace_connection(acceptance_context.bind_input(user_id, "b"))
    second = await load_connection(acceptance_context, user_id)
    secret_b = await service.get_active_connection_secret(user_id)
    stale = await service.mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=user_id,
            snapshot=secret_a.snapshot,
            reason="authentication_failed",
        )
    )
    before_disable = connection_snapshot(await load_connection(acceptance_context, user_id))
    await service.disable_connection(user_id)
    after_disable = await load_connection(acceptance_context, user_id)

    assert second.last_verified_at == t2
    assert secret_a.snapshot.connection_id == secret_b.snapshot.connection_id
    assert (
        secret_a.snapshot.token_encryption_version
        == secret_b.snapshot.token_encryption_version
        == 1
    )
    assert secret_a.snapshot.encrypted_api_token != secret_b.snapshot.encrypted_api_token
    assert stale is None
    assert after_disable.last_verified_at == before_disable[8]
    assert secret_b.snapshot.connection_id == second.id
    assert secret_b.snapshot.encrypted_api_token == bytes(second.encrypted_api_token)
    assert secret_b.snapshot.token_encryption_version == second.token_encryption_version
    with pytest.raises(FrozenInstanceError):
        secret_b.snapshot.token_encryption_version = 2  # type: ignore[misc]
    assert bytes(second.encrypted_api_token).decode("ascii") not in repr(secret_b.snapshot)


@pytest.mark.asyncio
async def test_current_disabled_and_missing_snapshot_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    user_id = await create_user(acceptance_context)
    service = acceptance_context.connection_service()
    await service.bind_or_replace_connection(acceptance_context.bind_input(user_id, "a"))
    secret = await service.get_active_connection_secret(user_id)
    current = await service.mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=user_id,
            snapshot=secret.snapshot,
            reason="authentication_failed",
        )
    )
    repeated = await service.mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=user_id,
            snapshot=secret.snapshot,
            reason="authentication_failed",
        )
    )
    assert current is not None and current.status == "NEEDS_REAUTH"
    assert repeated is not None and repeated.status == "NEEDS_REAUTH"

    await service.disable_connection(user_id)
    disabled_connection = await load_connection(acceptance_context, user_id)
    disabled_snapshot = KaitenCredentialSnapshot(
        connection_id=disabled_connection.id,
        encrypted_api_token=bytes(disabled_connection.encrypted_api_token),
        token_encryption_version=disabled_connection.token_encryption_version,
    )
    disabled = await service.mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=user_id,
            snapshot=disabled_snapshot,
            reason="authentication_failed",
        )
    )
    missing = await service.mark_needs_reauth(
        MarkKaitenNeedsReauthInput(
            user_id=uuid.uuid4(),
            snapshot=disabled_snapshot,
            reason="authentication_failed",
        )
    )

    assert disabled is not None and disabled.status == "DISABLED"
    assert missing is None


@pytest.mark.asyncio
async def test_crypto_rotation_unknown_version_and_tampered_ciphertext_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    user_id = await create_user(acceptance_context)
    key_v1 = Fernet.generate_key().decode("ascii")
    key_v2 = Fernet.generate_key().decode("ascii")
    cipher_v1 = VersionedFernetTokenCipher(keys={1: key_v1}, active_version=1)
    service_v1 = acceptance_context.connection_service(cipher=cipher_v1)
    await service_v1.bind_or_replace_connection(acceptance_context.bind_input(user_id, "a"))

    rotated_cipher = VersionedFernetTokenCipher(keys={1: key_v1, 2: key_v2}, active_version=2)
    rotated_service = acceptance_context.connection_service(cipher=rotated_cipher)
    old_secret = await rotated_service.get_active_connection_secret(user_id)
    await rotated_service.bind_or_replace_connection(acceptance_context.bind_input(user_id, "b"))
    version_2_connection = await load_connection(acceptance_context, user_id)
    assert old_secret.plaintext_token.endswith("-token-a")
    assert version_2_connection.token_encryption_version == 2
    assert rotated_cipher.decrypt(
        bytes(version_2_connection.encrypted_api_token),
        version_2_connection.token_encryption_version,
    ).endswith("-token-b")

    before_unknown = connection_snapshot(version_2_connection)
    await set_connection_ciphertext_and_version(
        acceptance_context,
        user_id,
        ciphertext=bytes(version_2_connection.encrypted_api_token),
        version=99,
    )
    with pytest.raises(CredentialDecryptionFailed):
        await rotated_service.get_active_connection_secret(user_id)
    assert connection_snapshot(await load_connection(acceptance_context, user_id))[7] == "ACTIVE"

    await set_connection_ciphertext_and_version(
        acceptance_context,
        user_id,
        ciphertext=before_unknown[5],
        version=before_unknown[6],
    )
    await set_connection_ciphertext_and_version(
        acceptance_context,
        user_id,
        ciphertext=bytes(before_unknown[5])[:-1] + b"A",
        version=2,
    )
    with pytest.raises(CredentialDecryptionFailed):
        await rotated_service.get_active_connection_secret(user_id)
    assert connection_snapshot(await load_connection(acceptance_context, user_id))[7] == "ACTIVE"


@pytest.mark.asyncio
async def test_concurrent_identity_onboarding_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    identity_service = IdentityService(acceptance_context.sessionmaker)
    input = acceptance_context.identity_input("race", "race-chat")

    first, second = await asyncio.gather(
        identity_service.resolve_or_onboard_private_max_user(input),
        identity_service.resolve_or_onboard_private_max_user(input),
    )
    await record_user(acceptance_context, first.user_id)

    assert first.user_id == second.user_id
    assert first.max_chat_binding_id == second.max_chat_binding_id
    assert await settings_count(acceptance_context, first.user_id) == 1
    binding = await load_binding(acceptance_context, input.max_user_id)
    assert binding.id == first.max_chat_binding_id


@pytest.mark.asyncio
async def test_concurrent_bind_replacement_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    user_id = await create_user(acceptance_context)
    cipher = acceptance_context.cipher()
    first = acceptance_context.connection_service(
        verifier=FakeVerifier(kaiten_user_id="first"),
        cipher=cipher,
        clock=FixedClock(datetime(2026, 8, 16, 10, tzinfo=UTC)),
    )
    second = acceptance_context.connection_service(
        verifier=FakeVerifier(kaiten_user_id="second"),
        cipher=cipher,
        clock=FixedClock(datetime(2026, 8, 16, 11, tzinfo=UTC)),
    )

    results = await asyncio.gather(
        first.bind_or_replace_connection(acceptance_context.bind_input(user_id, "first")),
        second.bind_or_replace_connection(acceptance_context.bind_input(user_id, "second")),
    )
    connection = await load_connection(acceptance_context, user_id)

    assert len({result.connection_id for result in results}) == 1
    assert await connection_count(acceptance_context, user_id) == 1
    assert connection.status == "ACTIVE"
    assert connection.kaiten_user_id in {"first", "second"}
    assert connection.last_verified_at in {
        datetime(2026, 8, 16, 10, tzinfo=UTC),
        datetime(2026, 8, 16, 11, tzinfo=UTC),
    }


@pytest.mark.asyncio
async def test_in_flight_user_disable_acceptance(
    acceptance_context: AcceptanceContext,
) -> None:
    user_id = await create_user(acceptance_context)

    class DisablingVerifier(FakeVerifier):
        async def verify(
            self,
            *,
            api_base_url: str,
            plaintext_token: str,
        ) -> KaitenCredentialVerification:
            await set_user_status(acceptance_context, user_id, "DISABLED")
            return await super().verify(api_base_url=api_base_url, plaintext_token=plaintext_token)

    service = acceptance_context.connection_service(verifier=DisablingVerifier())

    with pytest.raises(UserDisabled):
        await service.bind_or_replace_connection(acceptance_context.bind_input(user_id, "a"))

    async with acceptance_context.sessionmaker() as session:
        assert await KaitenConnectionRepository(session).get_for_user(user_id) is None


@pytest.mark.asyncio
async def test_application_service_acceptance_database_returns_to_baseline(
    acceptance_context: AcceptanceContext,
) -> None:
    assert await table_counts(acceptance_context.engine) == acceptance_context.baseline_counts
