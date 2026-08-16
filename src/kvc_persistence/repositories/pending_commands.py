"""Pending command repository primitives."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kvc_persistence.models import ACTIVE_PENDING_STATES, PendingCommand
from kvc_persistence.repositories._statements import (
    select_active_pending_command_for_update,
    select_dialog_session_for_update,
)
from kvc_persistence.repositories.contracts import PersistenceInvariantError
from kvc_persistence.repositories.users import _scalar_one_or_none


class PendingCommandRepository:
    """Persistence primitives for durable transient command workflow state."""

    _UPDATE_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "arguments",
            "unresolved_entity",
            "candidates",
            "state",
            "failure_reason",
            "clarification_attempts",
            "expires_at",
            "executed_at",
        }
    )

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_for_session(
        self,
        dialog_session_id: uuid.UUID,
    ) -> PendingCommand | None:
        return await _scalar_one_or_none(
            self._session,
            select(PendingCommand).where(
                PendingCommand.dialog_session_id == dialog_session_id,
                PendingCommand.state.in_(ACTIVE_PENDING_STATES),
            ),
        )

    async def get_active_for_session_for_update(
        self,
        dialog_session_id: uuid.UUID,
    ) -> PendingCommand | None:
        return await _scalar_one_or_none(
            self._session,
            select_active_pending_command_for_update(dialog_session_id),
        )

    async def create_active(
        self,
        *,
        user_id: uuid.UUID,
        dialog_session_id: uuid.UUID,
        intent: str,
        original_message: str,
        command_id: uuid.UUID | None = None,
        arguments: dict[str, Any] | None = None,
        unresolved_entity: dict[str, Any] | None = None,
        candidates: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> PendingCommand:
        dialog_session = await _scalar_one_or_none(
            self._session,
            select_dialog_session_for_update(dialog_session_id),
        )
        if dialog_session is None:
            raise PersistenceInvariantError(
                f"Cannot create pending command for missing dialog session: "
                f"dialog_session_id={dialog_session_id}"
            )
        if dialog_session.user_id != user_id:
            raise PersistenceInvariantError(
                "Pending command ownership mismatch: "
                f"user_id={user_id}, dialog_session_id={dialog_session_id}"
            )

        existing = await self.get_active_for_session(dialog_session_id)
        if existing is not None:
            return existing

        command = PendingCommand(
            user_id=user_id,
            dialog_session_id=dialog_session_id,
            intent=intent,
            original_message=original_message,
            unresolved_entity=unresolved_entity,
            candidates=candidates,
            expires_at=expires_at,
        )
        if command_id is not None:
            command.id = command_id
        if arguments is not None:
            command.arguments = arguments

        self._session.add(command)
        await self._session.flush()
        await self._session.refresh(command)
        return command

    async def update_resolution_state(
        self,
        command: PendingCommand,
        *,
        state: str,
        unresolved_entity: dict[str, Any] | None = None,
        candidates: dict[str, Any] | None = None,
        clarification_attempts: int | None = None,
        failure_reason: str | None = None,
        expires_at: datetime | None = None,
        executed_at: datetime | None = None,
    ) -> PendingCommand:
        command.state = state
        command.unresolved_entity = unresolved_entity
        command.candidates = candidates
        command.failure_reason = failure_reason
        command.expires_at = expires_at
        command.executed_at = executed_at
        if clarification_attempts is not None:
            command.clarification_attempts = clarification_attempts
        await self._session.flush()
        await self._session.refresh(command)
        return command

    async def update_fields(self, command: PendingCommand, **fields: object) -> PendingCommand:
        unknown_fields = set(fields) - self._UPDATE_FIELDS
        if unknown_fields:
            unknown = ", ".join(sorted(unknown_fields))
            raise PersistenceInvariantError(f"Unsupported pending command field(s): {unknown}")

        for field, value in fields.items():
            setattr(command, field, value)
        await self._session.flush()
        await self._session.refresh(command)
        return command
