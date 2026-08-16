"""Live PostgreSQL integration tests for repository/query contracts."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from kvc_config import get_settings
from kvc_persistence import (
    create_async_engine_from_settings,
    create_async_sessionmaker,
    dispose_async_engine,
)
from kvc_persistence.models import DialogSession, PendingCommand
from kvc_persistence.repositories import (
    DialogSessionRepository,
    KaitenConnectionRepository,
    MaxChatRepository,
    NotificationHistoryRepository,
    NotificationSettingsRepository,
    PendingCommandRepository,
    PersistenceInvariantError,
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


@pytest_asyncio.fixture
async def live_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    if settings.app_env != "development":
        pytest.skip("Repository integration tests require KVC_APP_ENV=development.")

    engine = create_async_engine_from_settings(settings)
    try:
        async with engine.connect() as conn:
            database_name = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            if database_name != "kvc_dev":
                pytest.skip("Repository integration tests require the kvc_dev database.")

            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
            if revision != EXPECTED_REVISION:
                pytest.skip("Repository integration tests require the accepted Alembic head.")

        yield engine
    finally:
        await dispose_async_engine(engine)


@pytest_asyncio.fixture
async def db_session(live_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    session_factory = create_async_sessionmaker(live_engine)
    async with session_factory() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()
            else:
                await session.rollback()


async def table_counts(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as conn:
        counts = {}
        for table_name in BUSINESS_TABLES:
            counts[table_name] = (
                await conn.execute(text(f"SELECT count(*) FROM {table_name}"))
            ).scalar_one()
        return counts


async def create_user(session: AsyncSession, user_id: uuid.UUID | None = None) -> uuid.UUID:
    user = await UserRepository(session).create(user_id=user_id)
    return user.id


@pytest.mark.asyncio
async def test_user_repository_create_get_lock_and_status_update(
    db_session: AsyncSession,
) -> None:
    user_repository = UserRepository(db_session)
    user_id = uuid.uuid4()

    user = await user_repository.create(user_id=user_id)
    assert user.status == "ACTIVE"

    assert (await user_repository.get_by_id(user_id)) is user
    locked = await user_repository.get_by_id_for_update(user_id)
    assert locked is user

    updated = await user_repository.set_status(user, "DISABLED")
    assert updated.status == "DISABLED"


@pytest.mark.asyncio
async def test_repository_methods_do_not_commit_and_caller_rollback_removes_rows(
    live_engine: AsyncEngine,
) -> None:
    session_factory = create_async_sessionmaker(live_engine)
    user_id = uuid.uuid4()

    async with session_factory() as session:
        transaction = await session.begin()
        await UserRepository(session).create(user_id=user_id)
        await transaction.rollback()

    async with session_factory() as verification_session:
        assert await UserRepository(verification_session).get_by_id(user_id) is None


@pytest.mark.asyncio
async def test_max_chat_repository_private_binding_queries(db_session: AsyncSession) -> None:
    user_id = await create_user(db_session)
    repository = MaxChatRepository(db_session)

    binding = await repository.create_private_binding(
        user_id=user_id,
        max_user_id=f"synthetic-max-user-{uuid.uuid4()}",
        max_chat_id=f"synthetic-max-chat-{uuid.uuid4()}",
    )

    assert await repository.get_by_max_chat_id(binding.max_chat_id) is binding
    assert await repository.get_private_by_max_user_id(binding.max_user_id) is binding
    assert await repository.get_primary_for_user(user_id) is binding
    assert binding.chat_type == "PRIVATE"


@pytest.mark.asyncio
async def test_kaiten_connection_repository_stores_only_encrypted_bytes(
    db_session: AsyncSession,
) -> None:
    user_id = await create_user(db_session)
    repository = KaitenConnectionRepository(db_session)

    connection = await repository.create(
        user_id=user_id,
        api_base_url="https://synthetic.example/api/latest",
        encrypted_api_token=b"synthetic-ciphertext-v1",
        kaiten_user_id="synthetic-kaiten-user",
        workspace_id="synthetic-workspace",
    )

    assert await repository.get_for_user(user_id) is connection
    assert await repository.get_for_user_for_update(user_id) is connection
    assert connection.encrypted_api_token == b"synthetic-ciphertext-v1"

    updated = await repository.update_connection(
        connection,
        api_base_url="https://synthetic.example/api/latest",
        encrypted_api_token=b"synthetic-ciphertext-v2",
        token_encryption_version=2,
        status="NEEDS_REAUTH",
        kaiten_user_id=None,
        workspace_id=None,
        last_verified_at=datetime.now(UTC),
    )
    assert updated.user_id == user_id
    assert updated.encrypted_api_token == b"synthetic-ciphertext-v2"
    assert updated.status == "NEEDS_REAUTH"


@pytest.mark.asyncio
async def test_dialog_repository_active_session_lifecycle(db_session: AsyncSession) -> None:
    user_id = await create_user(db_session)
    repository = DialogSessionRepository(db_session)

    first = await repository.get_or_create_active(user_id=user_id)
    same = await repository.get_or_create_active(user_id=user_id)
    assert same.id == first.id
    assert await repository.get_active_for_user(user_id) is same
    assert await repository.get_active_for_user_for_update(user_id) is same

    await repository.update_context(
        same,
        current_board_id="synthetic-board",
        current_board_name="Synthetic board",
        last_card_list={"version": 1, "source": "cards.list", "items": []},
        last_card_list_at=datetime.now(UTC),
    )
    assert same.current_board_id == "synthetic-board"
    assert same.last_card_list == {"version": 1, "source": "cards.list", "items": []}

    await repository.end(same, datetime.now(UTC))
    second = await repository.get_or_create_active(user_id=user_id)
    assert second.id != first.id


@pytest.mark.asyncio
async def test_dialog_update_context_rejects_unaccepted_fields(
    db_session: AsyncSession,
) -> None:
    user_id = await create_user(db_session)
    session = await DialogSessionRepository(db_session).get_or_create_active(user_id=user_id)

    with pytest.raises(PersistenceInvariantError, match="Unsupported dialog context"):
        await DialogSessionRepository(db_session).update_context(session, transcript=[])


@pytest.mark.asyncio
async def test_pending_command_repository_ownership_and_active_contracts(
    db_session: AsyncSession,
) -> None:
    first_user_id = await create_user(db_session)
    second_user_id = await create_user(db_session)
    dialog = await DialogSessionRepository(db_session).get_or_create_active(user_id=first_user_id)
    repository = PendingCommandRepository(db_session)

    command = await repository.create_active(
        user_id=first_user_id,
        dialog_session_id=dialog.id,
        intent="synthetic.intent",
        original_message="synthetic message",
    )
    assert command.user_id == first_user_id
    assert command.dialog_session_id == dialog.id
    assert command.state == "RECEIVED"
    assert command.arguments == {"version": 1, "payload": {}}
    assert await repository.get_active_for_session(dialog.id) is command
    assert await repository.get_active_for_session_for_update(dialog.id) is command

    duplicate = await repository.create_active(
        user_id=first_user_id,
        dialog_session_id=dialog.id,
        intent="synthetic.intent.duplicate",
        original_message="duplicate synthetic message",
    )
    assert duplicate.id == command.id

    with pytest.raises(PersistenceInvariantError, match="ownership mismatch"):
        await repository.create_active(
            user_id=second_user_id,
            dialog_session_id=dialog.id,
            intent="synthetic.intent",
            original_message="mismatched synthetic message",
        )

    await repository.update_resolution_state(
        command, state="EXECUTED", executed_at=datetime.now(UTC)
    )
    next_command = await repository.create_active(
        user_id=first_user_id,
        dialog_session_id=dialog.id,
        intent="synthetic.intent.next",
        original_message="next synthetic message",
    )
    assert next_command.id != command.id


@pytest.mark.asyncio
async def test_pending_command_partial_unique_remains_final_guard(
    db_session: AsyncSession,
) -> None:
    user_id = await create_user(db_session)
    dialog = await DialogSessionRepository(db_session).get_or_create_active(user_id=user_id)
    command = await PendingCommandRepository(db_session).create_active(
        user_id=user_id,
        dialog_session_id=dialog.id,
        intent="synthetic.intent",
        original_message="synthetic message",
    )

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                PendingCommand(
                    user_id=user_id,
                    dialog_session_id=dialog.id,
                    intent="synthetic.intent.direct",
                    original_message="direct duplicate",
                )
            )
            await db_session.flush()

    assert await PendingCommandRepository(db_session).get_active_for_session(dialog.id) is command


@pytest.mark.asyncio
async def test_dialog_partial_unique_remains_final_guard(db_session: AsyncSession) -> None:
    user_id = await create_user(db_session)
    session = await DialogSessionRepository(db_session).get_or_create_active(user_id=user_id)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(DialogSession(user_id=user_id))
            await db_session.flush()

    assert await DialogSessionRepository(db_session).get_active_for_user(user_id) is session


@pytest.mark.asyncio
async def test_notification_settings_repository_defaults_and_enabled_order(
    db_session: AsyncSession,
) -> None:
    first_user_id = uuid.UUID("00000000-0000-4000-8000-000000000001")
    second_user_id = uuid.UUID("00000000-0000-4000-8000-000000000002")
    await create_user(db_session, first_user_id)
    await create_user(db_session, second_user_id)
    repository = NotificationSettingsRepository(db_session)

    first = await repository.get_or_create_for_user(first_user_id)
    second = await repository.get_or_create_for_user(second_user_id)
    assert await repository.get_for_user(first_user_id) is first
    assert await repository.get_for_user_for_update(first_user_id) is first
    assert first.enabled is False
    assert first.due_soon_days == 1
    assert first.timezone == "UTC"

    second.enabled = True
    first.enabled = True
    await db_session.flush()

    enabled = await repository.list_enabled()
    assert [settings.user_id for settings in enabled] == [first_user_id, second_user_id]


@pytest.mark.asyncio
async def test_notification_history_repository_reserve_dedup_and_status_updates(
    db_session: AsyncSession,
) -> None:
    user_id = await create_user(db_session)
    repository = NotificationHistoryRepository(db_session)
    due_at = datetime(2026, 9, 20, tzinfo=UTC)

    first = await repository.reserve(
        user_id=user_id,
        kaiten_card_id="synthetic-kaiten-card",
        due_at=due_at,
        due_date_time_present=False,
        notification_type="DUE_TODAY",
    )
    assert first is not None
    assert first.delivery_status == "RESERVED"
    assert first.due_at == due_at
    assert first.due_date_time_present is False

    duplicate = await repository.reserve(
        user_id=user_id,
        kaiten_card_id="synthetic-kaiten-card",
        due_at=due_at,
        due_date_time_present=False,
        notification_type="DUE_TODAY",
    )
    assert duplicate is None

    different_due_at = await repository.reserve(
        user_id=user_id,
        kaiten_card_id="synthetic-kaiten-card",
        due_at=due_at + timedelta(hours=1),
        due_date_time_present=False,
        notification_type="DUE_TODAY",
    )
    assert different_due_at is not None
    assert different_due_at.id != first.id

    by_key = await repository.get_by_dedup_key(
        user_id=user_id,
        kaiten_card_id="synthetic-kaiten-card",
        due_at=due_at,
        due_date_time_present=False,
        notification_type="DUE_TODAY",
    )
    assert by_key is first
    assert (
        await repository.get_by_id_for_update(user_id=user_id, notification_history_id=first.id)
        is first
    )

    sent_at = datetime.now(UTC)
    await repository.mark_sent(first, sent_at=sent_at)
    assert first.delivery_status == "SENT"
    assert first.sent_at == sent_at

    failed_at = sent_at + timedelta(minutes=1)
    await repository.mark_failed(first, failed_at=failed_at, error_type="synthetic_error")
    assert first.delivery_status == "FAILED"
    assert first.failed_at == failed_at
    assert first.error_type == "synthetic_error"


@pytest.mark.asyncio
async def test_user_scoped_notification_history_does_not_cross_user_boundary(
    db_session: AsyncSession,
) -> None:
    first_user_id = await create_user(db_session)
    second_user_id = await create_user(db_session)
    repository = NotificationHistoryRepository(db_session)

    reserved = await repository.reserve(
        user_id=first_user_id,
        kaiten_card_id="synthetic-isolation-card",
        due_at=datetime(2026, 9, 20, tzinfo=UTC),
        due_date_time_present=True,
        notification_type="DUE_SOON",
    )
    assert reserved is not None

    assert (
        await repository.get_by_id_for_update(
            user_id=second_user_id,
            notification_history_id=reserved.id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_repository_integration_database_stays_clean(live_engine: AsyncEngine) -> None:
    assert await table_counts(live_engine) == {table_name: 0 for table_name in BUSINESS_TABLES}
