"""MAX chat binding repository primitives."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kvc_persistence.models import MaxChat
from kvc_persistence.repositories.users import _scalar_one_or_none


class MaxChatRepository:
    """Persistence primitives for MAX private chat bindings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_max_chat_id(self, max_chat_id: str) -> MaxChat | None:
        return await _scalar_one_or_none(
            self._session,
            select(MaxChat).where(MaxChat.max_chat_id == max_chat_id),
        )

    async def get_private_by_max_user_id(self, max_user_id: str) -> MaxChat | None:
        return await _scalar_one_or_none(
            self._session,
            select(MaxChat).where(
                MaxChat.max_user_id == max_user_id,
                MaxChat.chat_type == "PRIVATE",
            ),
        )

    async def get_private_by_max_user_id_for_update(self, max_user_id: str) -> MaxChat | None:
        return await _scalar_one_or_none(
            self._session,
            select(MaxChat)
            .where(
                MaxChat.max_user_id == max_user_id,
                MaxChat.chat_type == "PRIVATE",
            )
            .with_for_update(),
        )

    async def get_primary_for_user(self, user_id: uuid.UUID) -> MaxChat | None:
        return await _scalar_one_or_none(
            self._session,
            select(MaxChat).where(MaxChat.user_id == user_id, MaxChat.is_primary.is_(True)),
        )

    async def create_private_binding(
        self,
        *,
        user_id: uuid.UUID,
        max_user_id: str,
        max_chat_id: str,
        binding_id: uuid.UUID | None = None,
        is_primary: bool = True,
    ) -> MaxChat:
        binding = MaxChat(
            user_id=user_id,
            max_user_id=max_user_id,
            max_chat_id=max_chat_id,
            chat_type="PRIVATE",
            is_primary=is_primary,
        )
        if binding_id is not None:
            binding.id = binding_id

        self._session.add(binding)
        await self._session.flush()
        await self._session.refresh(binding)
        return binding

    async def update_max_chat_id(self, binding: MaxChat, max_chat_id: str) -> MaxChat:
        binding.max_chat_id = max_chat_id
        await self._session.flush()
        await self._session.refresh(binding)
        return binding
