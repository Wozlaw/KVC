"""Dialog session repository primitives."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kvc_persistence.models import DialogSession
from kvc_persistence.repositories._statements import select_active_dialog_for_update
from kvc_persistence.repositories.contracts import PersistenceInvariantError
from kvc_persistence.repositories.users import UserRepository, _scalar_one_or_none


class DialogSessionRepository:
    """Persistence primitives for bounded restart-safe dialog context."""

    _CONTEXT_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "max_chat_binding_id",
            "current_board_id",
            "current_board_name",
            "current_card_id",
            "current_card_title",
            "previous_user_message",
            "previous_bot_message",
            "last_card_list",
            "last_card_list_at",
            "expires_at",
        }
    )

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_for_user(self, user_id: uuid.UUID) -> DialogSession | None:
        return await _scalar_one_or_none(
            self._session,
            select(DialogSession).where(
                DialogSession.user_id == user_id,
                DialogSession.ended_at.is_(None),
            ),
        )

    async def get_active_for_user_for_update(self, user_id: uuid.UUID) -> DialogSession | None:
        return await _scalar_one_or_none(self._session, select_active_dialog_for_update(user_id))

    async def get_or_create_active(
        self,
        *,
        user_id: uuid.UUID,
        max_chat_binding_id: uuid.UUID | None = None,
        expires_at: datetime | None = None,
    ) -> DialogSession:
        user = await UserRepository(self._session).get_by_id_for_update(user_id)
        if user is None:
            raise PersistenceInvariantError(
                f"Cannot create active dialog for missing user: user_id={user_id}"
            )

        existing = await self.get_active_for_user(user_id)
        if existing is not None:
            return existing

        session = DialogSession(
            user_id=user_id,
            max_chat_binding_id=max_chat_binding_id,
            expires_at=expires_at,
        )
        self._session.add(session)
        await self._session.flush()
        await self._session.refresh(session)
        return session

    async def update_context(
        self, dialog_session: DialogSession, **fields: object
    ) -> DialogSession:
        unknown_fields = set(fields) - self._CONTEXT_FIELDS
        if unknown_fields:
            unknown = ", ".join(sorted(unknown_fields))
            raise PersistenceInvariantError(f"Unsupported dialog context field(s): {unknown}")

        for field, value in fields.items():
            setattr(dialog_session, field, value)
        await self._session.flush()
        await self._session.refresh(dialog_session)
        return dialog_session

    async def end(self, dialog_session: DialogSession, ended_at: datetime) -> DialogSession:
        dialog_session.ended_at = ended_at
        await self._session.flush()
        await self._session.refresh(dialog_session)
        return dialog_session
