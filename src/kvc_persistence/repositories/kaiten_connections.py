"""Kaiten connection repository primitives."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kvc_persistence.models import KaitenConnection
from kvc_persistence.repositories.users import _scalar_one_or_none


class KaitenConnectionRepository:
    """Persistence primitives for encrypted per-user Kaiten connection settings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, user_id: uuid.UUID) -> KaitenConnection | None:
        return await _scalar_one_or_none(
            self._session,
            select(KaitenConnection).where(KaitenConnection.user_id == user_id),
        )

    async def get_for_user_for_update(self, user_id: uuid.UUID) -> KaitenConnection | None:
        return await _scalar_one_or_none(
            self._session,
            select(KaitenConnection).where(KaitenConnection.user_id == user_id).with_for_update(),
        )

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        api_base_url: str,
        encrypted_api_token: bytes,
        connection_id: uuid.UUID | None = None,
        kaiten_user_id: str | None = None,
        workspace_id: str | None = None,
        token_encryption_version: int = 1,
        status: str = "ACTIVE",
        last_verified_at: datetime | None = None,
    ) -> KaitenConnection:
        connection = KaitenConnection(
            user_id=user_id,
            api_base_url=api_base_url,
            kaiten_user_id=kaiten_user_id,
            workspace_id=workspace_id,
            encrypted_api_token=encrypted_api_token,
            token_encryption_version=token_encryption_version,
            status=status,
            last_verified_at=last_verified_at,
        )
        if connection_id is not None:
            connection.id = connection_id

        self._session.add(connection)
        await self._session.flush()
        await self._session.refresh(connection)
        return connection

    async def update_connection(
        self,
        connection: KaitenConnection,
        *,
        api_base_url: str,
        encrypted_api_token: bytes,
        token_encryption_version: int,
        status: str,
        kaiten_user_id: str | None = None,
        workspace_id: str | None = None,
        last_verified_at: datetime | None = None,
    ) -> KaitenConnection:
        connection.api_base_url = api_base_url
        connection.encrypted_api_token = encrypted_api_token
        connection.token_encryption_version = token_encryption_version
        connection.status = status
        connection.kaiten_user_id = kaiten_user_id
        connection.workspace_id = workspace_id
        connection.last_verified_at = last_verified_at
        await self._session.flush()
        await self._session.refresh(connection)
        return connection
