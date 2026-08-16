"""Structural repository contract tests."""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.dialects import postgresql

from kvc_persistence.repositories import (
    DialogSessionRepository,
    NotificationHistoryRepository,
    PendingCommandRepository,
    PersistenceInvariantError,
)
from kvc_persistence.repositories._statements import (
    insert_notification_reservation,
    select_active_dialog_for_update,
    select_active_pending_command_for_update,
    select_dialog_session_for_update,
    select_user_for_update,
)


def compile_postgresql(statement: object) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_repository_package_imports() -> None:
    assert DialogSessionRepository
    assert NotificationHistoryRepository
    assert PendingCommandRepository
    assert PersistenceInvariantError


def test_repository_sources_do_not_own_transaction_lifecycle() -> None:
    repository_dir = Path("src/kvc_persistence/repositories")

    for path in repository_dir.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert ".commit(" not in source
        assert ".rollback(" not in source


def test_lock_statement_helpers_compile_to_for_update() -> None:
    user_id = uuid.uuid4()
    dialog_session_id = uuid.uuid4()

    assert "FOR UPDATE" in compile_postgresql(select_user_for_update(user_id))
    assert "FOR UPDATE" in compile_postgresql(select_active_dialog_for_update(user_id))
    assert "FOR UPDATE" in compile_postgresql(select_dialog_session_for_update(dialog_session_id))
    assert "FOR UPDATE" in compile_postgresql(
        select_active_pending_command_for_update(dialog_session_id)
    )


def test_dialog_get_or_create_uses_parent_user_lock_pattern() -> None:
    source = inspect.getsource(DialogSessionRepository.get_or_create_active)

    assert "get_by_id_for_update" in source
    assert "get_active_for_user" in source


def test_pending_create_active_locks_dialog_session_before_insert() -> None:
    source = inspect.getsource(PendingCommandRepository.create_active)

    assert "select_dialog_session_for_update" in source
    assert "dialog_session.user_id != user_id" in source


def test_notification_reservation_uses_postgresql_on_conflict_do_nothing() -> None:
    statement = insert_notification_reservation(
        user_id=uuid.uuid4(),
        kaiten_card_id="synthetic-card",
        due_at=datetime(2026, 9, 20, tzinfo=UTC),
        due_date_time_present=False,
        notification_type="DUE_TODAY",
    )
    compiled = compile_postgresql(statement)

    assert "INSERT INTO notification_history" in compiled
    assert "ON CONFLICT ON CONSTRAINT uq_notification_history_dedup DO NOTHING" in compiled
    assert "RETURNING" in compiled


def test_repositories_do_not_define_plaintext_kaiten_token_path() -> None:
    repository_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("src/kvc_persistence/repositories").rglob("*.py")
    )

    assert "plaintext" not in repository_source.lower()
    assert "encrypted_api_token" in repository_source
