"""Kaiten credential connection lifecycle service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kvc_application.dto import (
    ActiveKaitenConnectionSecret,
    BindKaitenConnectionInput,
    KaitenConnectionResult,
    KaitenConnectionStatus,
    KaitenCredentialSnapshot,
    MarkKaitenNeedsReauthInput,
    UserStatus,
)
from kvc_application.errors import (
    KaitenConnectionDisabled,
    KaitenConnectionMissing,
    KaitenConnectionNeedsReauth,
    PersistenceConflict,
    UserDisabled,
)
from kvc_application.ports import Clock, KaitenCredentialVerifier, TokenCipher
from kvc_persistence.models import KaitenConnection
from kvc_persistence.repositories import (
    KaitenConnectionRepository,
    PersistenceInvariantError,
    UserRepository,
)


class KaitenConnectionService:
    """Verified encrypted Kaiten credential lifecycle operations."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        verifier: KaitenCredentialVerifier,
        token_cipher: TokenCipher,
        clock: Clock,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._verifier = verifier
        self._token_cipher = token_cipher
        self._clock = clock

    async def bind_or_replace_connection(
        self,
        input: BindKaitenConnectionInput,
    ) -> KaitenConnectionResult:
        await self._preflight_active_user(input.user_id)

        verification = await self._verifier.verify(
            api_base_url=input.api_base_url,
            plaintext_token=input.plaintext_token,
        )
        encrypted = self._token_cipher.encrypt(input.plaintext_token)
        verified_at = self._clock.now()

        try:
            async with self._sessionmaker() as session:
                async with session.begin():
                    users = UserRepository(session)
                    connections = KaitenConnectionRepository(session)

                    user = await users.get_by_id_for_update(input.user_id)
                    if user is None:
                        raise PersistenceConflict("KVC user disappeared during connection bind")
                    if self._as_user_status(user.status) == "DISABLED":
                        raise UserDisabled("KVC user is disabled")

                    connection = await connections.get_for_user_for_update(input.user_id)
                    if connection is None:
                        connection = await connections.create(
                            user_id=input.user_id,
                            api_base_url=input.api_base_url,
                            kaiten_user_id=verification.kaiten_user_id,
                            workspace_id=verification.workspace_id,
                            encrypted_api_token=encrypted.ciphertext,
                            token_encryption_version=encrypted.version,
                            status="ACTIVE",
                            last_verified_at=verified_at,
                        )
                    else:
                        self._as_kaiten_connection_status(connection.status)
                        connection = await connections.update_connection(
                            connection,
                            api_base_url=input.api_base_url,
                            kaiten_user_id=verification.kaiten_user_id,
                            workspace_id=verification.workspace_id,
                            encrypted_api_token=encrypted.ciphertext,
                            token_encryption_version=encrypted.version,
                            status="ACTIVE",
                            last_verified_at=verified_at,
                        )

                    return self._to_result(connection)
        except (IntegrityError, PersistenceInvariantError) as exc:
            raise PersistenceConflict("Kaiten connection persistence conflict") from exc

    async def disable_connection(self, user_id: UUID) -> KaitenConnectionResult:
        try:
            async with self._sessionmaker() as session:
                async with session.begin():
                    users = UserRepository(session)
                    connections = KaitenConnectionRepository(session)

                    user = await users.get_by_id_for_update(user_id)
                    if user is None:
                        raise PersistenceConflict("KVC user is missing for connection disable")
                    self._as_user_status(user.status)

                    connection = await connections.get_for_user_for_update(user_id)
                    if connection is None:
                        raise KaitenConnectionMissing("Kaiten connection is missing")

                    status = self._as_kaiten_connection_status(connection.status)
                    if status != "DISABLED":
                        connection = await connections.update_connection(
                            connection,
                            api_base_url=connection.api_base_url,
                            kaiten_user_id=connection.kaiten_user_id,
                            workspace_id=connection.workspace_id,
                            encrypted_api_token=bytes(connection.encrypted_api_token),
                            token_encryption_version=connection.token_encryption_version,
                            status="DISABLED",
                            last_verified_at=connection.last_verified_at,
                        )

                    return self._to_result(connection)
        except (IntegrityError, PersistenceInvariantError) as exc:
            raise PersistenceConflict("Kaiten connection persistence conflict") from exc

    async def get_active_connection_secret(self, user_id: UUID) -> ActiveKaitenConnectionSecret:
        async with self._sessionmaker() as session:
            async with session.begin():
                users = UserRepository(session)
                connections = KaitenConnectionRepository(session)

                user = await users.get_by_id_for_update(user_id)
                if user is None:
                    raise PersistenceConflict("KVC user is missing for connection secret")
                if self._as_user_status(user.status) == "DISABLED":
                    raise UserDisabled("KVC user is disabled")

                connection = await connections.get_for_user_for_update(user_id)
                if connection is None:
                    raise KaitenConnectionMissing("Kaiten connection is missing")

                status = self._as_kaiten_connection_status(connection.status)
                if status == "DISABLED":
                    raise KaitenConnectionDisabled("Kaiten connection is disabled")
                if status == "NEEDS_REAUTH":
                    raise KaitenConnectionNeedsReauth("Kaiten connection needs reauthorization")

                snapshot = self._to_snapshot(connection)
                plaintext_token = self._token_cipher.decrypt(
                    bytes(connection.encrypted_api_token),
                    connection.token_encryption_version,
                )
                return ActiveKaitenConnectionSecret(
                    connection_id=connection.id,
                    user_id=connection.user_id,
                    api_base_url=connection.api_base_url,
                    plaintext_token=plaintext_token,
                    snapshot=snapshot,
                )

    async def mark_needs_reauth(
        self,
        input: MarkKaitenNeedsReauthInput,
    ) -> KaitenConnectionResult | None:
        try:
            async with self._sessionmaker() as session:
                async with session.begin():
                    connections = KaitenConnectionRepository(session)

                    connection = await connections.get_for_user_for_update(input.user_id)
                    if connection is None:
                        return None
                    if not self._snapshot_matches(connection, input.snapshot):
                        return None

                    status = self._as_kaiten_connection_status(connection.status)
                    if status == "ACTIVE":
                        connection = await connections.update_connection(
                            connection,
                            api_base_url=connection.api_base_url,
                            kaiten_user_id=connection.kaiten_user_id,
                            workspace_id=connection.workspace_id,
                            encrypted_api_token=bytes(connection.encrypted_api_token),
                            token_encryption_version=connection.token_encryption_version,
                            status="NEEDS_REAUTH",
                            last_verified_at=connection.last_verified_at,
                        )

                    return self._to_result(connection)
        except (IntegrityError, PersistenceInvariantError) as exc:
            raise PersistenceConflict("Kaiten connection persistence conflict") from exc

    async def _preflight_active_user(self, user_id: UUID) -> None:
        async with self._sessionmaker() as session:
            users = UserRepository(session)
            user = await users.get_by_id(user_id)
            if user is None:
                raise PersistenceConflict("KVC user is missing for connection bind")
            if self._as_user_status(user.status) == "DISABLED":
                raise UserDisabled("KVC user is disabled")

    def _to_result(self, connection: KaitenConnection) -> KaitenConnectionResult:
        return KaitenConnectionResult(
            connection_id=connection.id,
            user_id=connection.user_id,
            status=self._as_kaiten_connection_status(connection.status),
            api_base_url=connection.api_base_url,
            kaiten_user_id=connection.kaiten_user_id,
            workspace_id=connection.workspace_id,
            last_verified_at=connection.last_verified_at,
        )

    def _to_snapshot(self, connection: KaitenConnection) -> KaitenCredentialSnapshot:
        return KaitenCredentialSnapshot(
            connection_id=connection.id,
            encrypted_api_token=bytes(connection.encrypted_api_token),
            token_encryption_version=connection.token_encryption_version,
        )

    def _snapshot_matches(
        self,
        connection: KaitenConnection,
        snapshot: KaitenCredentialSnapshot,
    ) -> bool:
        return (
            connection.id == snapshot.connection_id
            and bytes(connection.encrypted_api_token) == snapshot.encrypted_api_token
            and connection.token_encryption_version == snapshot.token_encryption_version
        )

    def _as_user_status(self, status: str) -> UserStatus:
        if status == "ACTIVE":
            return "ACTIVE"
        if status == "DISABLED":
            return "DISABLED"
        raise PersistenceConflict("unsupported persisted user status")

    def _as_kaiten_connection_status(self, status: str) -> KaitenConnectionStatus:
        if status == "ACTIVE":
            return "ACTIVE"
        if status == "DISABLED":
            return "DISABLED"
        if status == "NEEDS_REAUTH":
            return "NEEDS_REAUTH"
        raise PersistenceConflict("unsupported persisted Kaiten connection status")
