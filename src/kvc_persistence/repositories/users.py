"""User repository primitives."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from kvc_persistence.models import User
from kvc_persistence.repositories._statements import select_user_for_update


async def _scalar_one_or_none[T](
    session: AsyncSession,
    statement: Select[tuple[T]],
) -> T | None:
    result = await session.execute(statement)
    return result.scalar_one_or_none()


class UserRepository:
    """Persistence primitives for internal KVC users."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await _scalar_one_or_none(self._session, select(User).where(User.id == user_id))

    async def get_by_id_for_update(self, user_id: uuid.UUID) -> User | None:
        return await _scalar_one_or_none(self._session, select_user_for_update(user_id))

    async def create(self, *, user_id: uuid.UUID | None = None, status: str | None = None) -> User:
        user = User()
        if user_id is not None:
            user.id = user_id
        if status is not None:
            user.status = status

        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def set_status(self, user: User, status: str) -> User:
        user.status = status
        await self._session.flush()
        await self._session.refresh(user)
        return user
