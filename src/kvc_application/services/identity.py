"""MAX private identity onboarding service."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kvc_application.dto import (
    IdentityResolution,
    KaitenConnectionStatus,
    ResolveMaxIdentityInput,
    UserStatus,
)
from kvc_application.errors import IdentityConflict, PersistenceConflict
from kvc_persistence.models import MaxChat
from kvc_persistence.repositories import (
    KaitenConnectionRepository,
    MaxChatRepository,
    NotificationSettingsRepository,
    PersistenceInvariantError,
    UserRepository,
)


class IdentityService:
    """Resolve or onboard a KVC user from a PRIVATE MAX identity."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._sessionmaker = sessionmaker

    async def resolve_or_onboard_private_max_user(
        self,
        input: ResolveMaxIdentityInput,
    ) -> IdentityResolution:
        try:
            return await self._resolve_once(input, allow_onboarding=True)
        except IntegrityError as exc:
            try:
                return await self._resolve_once(input, allow_onboarding=False)
            except IntegrityError as retry_exc:
                raise PersistenceConflict("identity onboarding persistence conflict") from retry_exc
            except PersistenceInvariantError as retry_exc:
                raise PersistenceConflict("identity onboarding persistence conflict") from retry_exc
            except PersistenceConflict:
                raise
            except IdentityConflict:
                raise
            raise PersistenceConflict("identity onboarding persistence conflict") from exc
        except PersistenceInvariantError as exc:
            raise PersistenceConflict("identity onboarding persistence conflict") from exc

    async def _resolve_once(
        self,
        input: ResolveMaxIdentityInput,
        *,
        allow_onboarding: bool,
    ) -> IdentityResolution:
        if input.chat_type != "PRIVATE":
            raise PersistenceConflict("unsupported MAX chat type")

        async with self._sessionmaker() as session:
            async with session.begin():
                users = UserRepository(session)
                max_chats = MaxChatRepository(session)
                notification_settings = NotificationSettingsRepository(session)
                kaiten_connections = KaitenConnectionRepository(session)

                binding_by_chat = await max_chats.get_by_max_chat_id(input.max_chat_id)
                if binding_by_chat is not None:
                    if binding_by_chat.max_user_id != input.max_user_id:
                        raise IdentityConflict("MAX identity binding conflict")
                    return await self._build_resolution(
                        users=users,
                        kaiten_connections=kaiten_connections,
                        binding=binding_by_chat,
                        is_new_user=False,
                    )

                binding_by_user = await max_chats.get_private_by_max_user_id(input.max_user_id)
                if binding_by_user is not None:
                    rotated = await self._rotate_existing_binding(
                        max_chats=max_chats,
                        input=input,
                    )
                    return await self._build_resolution(
                        users=users,
                        kaiten_connections=kaiten_connections,
                        binding=rotated,
                        is_new_user=False,
                    )

                if not allow_onboarding:
                    raise PersistenceConflict("identity onboarding persistence conflict")

                user = await users.create(status="ACTIVE")
                binding = await max_chats.create_private_binding(
                    user_id=user.id,
                    max_user_id=input.max_user_id,
                    max_chat_id=input.max_chat_id,
                )
                await notification_settings.get_or_create_for_user(user.id)
                return await self._build_resolution(
                    users=users,
                    kaiten_connections=kaiten_connections,
                    binding=binding,
                    is_new_user=True,
                )

    async def _rotate_existing_binding(
        self,
        *,
        max_chats: MaxChatRepository,
        input: ResolveMaxIdentityInput,
    ) -> MaxChat:
        binding = await max_chats.get_private_by_max_user_id_for_update(input.max_user_id)
        if binding is None:
            raise PersistenceConflict("MAX private binding disappeared during rotation")
        if binding.max_user_id != input.max_user_id or binding.chat_type != "PRIVATE":
            raise PersistenceConflict("unsupported persisted MAX binding state")

        incoming_chat_binding = await max_chats.get_by_max_chat_id(input.max_chat_id)
        if incoming_chat_binding is not None and incoming_chat_binding.id != binding.id:
            raise IdentityConflict("MAX identity binding conflict")
        if binding.max_chat_id != input.max_chat_id:
            binding = await max_chats.update_max_chat_id(binding, input.max_chat_id)
        return binding

    async def _build_resolution(
        self,
        *,
        users: UserRepository,
        kaiten_connections: KaitenConnectionRepository,
        binding: MaxChat,
        is_new_user: bool,
    ) -> IdentityResolution:
        user = await users.get_by_id(binding.user_id)
        if user is None:
            raise PersistenceConflict("persisted MAX binding references missing user")

        connection = await kaiten_connections.get_for_user(user.id)
        connection_status = (
            None if connection is None else self._as_kaiten_connection_status(connection.status)
        )

        return IdentityResolution(
            user_id=user.id,
            max_chat_binding_id=binding.id,
            user_status=self._as_user_status(user.status),
            is_new_user=is_new_user,
            kaiten_connection_status=connection_status,
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
