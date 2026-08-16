"""Structural tests for the MVP persistence models."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID

from kvc_persistence import models as _models
from kvc_persistence.base import Base

BUSINESS_TABLES = {
    "users",
    "max_chats",
    "kaiten_connections",
    "dialog_sessions",
    "pending_commands",
    "notification_settings",
    "notification_history",
}


def table(name: str):
    return Base.metadata.tables[name]


def columns(name: str) -> list[str]:
    return list(table(name).c.keys())


def check_names(name: str) -> set[str]:
    return {
        constraint.name
        for constraint in table(name).constraints
        if isinstance(constraint, CheckConstraint) and constraint.name is not None
    }


def unique_constraint_names(name: str) -> set[str]:
    return {
        constraint.name
        for constraint in table(name).constraints
        if isinstance(constraint, UniqueConstraint) and constraint.name is not None
    }


def indexes(name: str) -> dict[str, Index]:
    return {index.name: index for index in table(name).indexes if index.name is not None}


def compiled_where(index: Index) -> str:
    where = index.dialect_options["postgresql"]["where"]
    assert where is not None
    return str(where.compile(dialect=postgresql.dialect()))


def foreign_key(name: str, column_name: str) -> ForeignKeyConstraint:
    matches = [
        constraint
        for constraint in table(name).constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and list(constraint.columns.keys()) == [column_name]
    ]
    assert len(matches) == 1
    return matches[0]


def assert_type(name: str, column_name: str, expected_type: type[object]) -> None:
    assert isinstance(table(name).c[column_name].type, expected_type)


def test_exact_business_table_inventory() -> None:
    assert _models.User.__tablename__ == "users"
    assert set(Base.metadata.tables) == BUSINESS_TABLES
    forbidden_tables = {
        "boards",
        "spaces",
        "columns",
        "cards",
        "comments",
        "attachments",
        "card_states",
        "kaiten_due_dates",
    }
    assert set(Base.metadata.tables).isdisjoint(forbidden_tables)


def test_column_inventory() -> None:
    assert columns("users") == ["id", "status", "created_at", "updated_at"]
    assert columns("max_chats") == [
        "id",
        "user_id",
        "max_user_id",
        "max_chat_id",
        "chat_type",
        "is_primary",
        "created_at",
        "updated_at",
    ]
    assert columns("kaiten_connections") == [
        "id",
        "user_id",
        "api_base_url",
        "kaiten_user_id",
        "workspace_id",
        "encrypted_api_token",
        "token_encryption_version",
        "status",
        "last_verified_at",
        "created_at",
        "updated_at",
    ]
    assert columns("dialog_sessions") == [
        "id",
        "user_id",
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
        "ended_at",
        "created_at",
        "updated_at",
    ]
    assert columns("pending_commands") == [
        "id",
        "user_id",
        "dialog_session_id",
        "intent",
        "original_message",
        "arguments",
        "unresolved_entity",
        "candidates",
        "state",
        "failure_reason",
        "clarification_attempts",
        "expires_at",
        "executed_at",
        "created_at",
        "updated_at",
    ]
    assert columns("notification_settings") == [
        "user_id",
        "enabled",
        "due_soon_days",
        "timezone",
        "created_at",
        "updated_at",
    ]
    assert columns("notification_history") == [
        "id",
        "user_id",
        "kaiten_card_id",
        "due_at",
        "due_date_time_present",
        "notification_type",
        "delivery_status",
        "sent_at",
        "failed_at",
        "error_type",
        "created_at",
        "updated_at",
    ]


def test_primary_keys_and_nullability() -> None:
    expected_primary_keys = {
        "users": ["id"],
        "max_chats": ["id"],
        "kaiten_connections": ["id"],
        "dialog_sessions": ["id"],
        "pending_commands": ["id"],
        "notification_settings": ["user_id"],
        "notification_history": ["id"],
    }

    for table_name, pk_columns in expected_primary_keys.items():
        assert list(table(table_name).primary_key.columns.keys()) == pk_columns
        for column_name in pk_columns:
            assert table(table_name).c[column_name].nullable is False

    nullable_columns = {
        "kaiten_connections": {"kaiten_user_id", "workspace_id", "last_verified_at"},
        "dialog_sessions": {
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
            "ended_at",
        },
        "pending_commands": {
            "unresolved_entity",
            "candidates",
            "failure_reason",
            "expires_at",
            "executed_at",
        },
        "notification_history": {"sent_at", "failed_at", "error_type"},
    }
    for table_name in BUSINESS_TABLES:
        expected_nullable = nullable_columns.get(table_name, set())
        actual_nullable = {column.name for column in table(table_name).c if column.nullable}
        assert actual_nullable == expected_nullable


def test_column_types() -> None:
    for table_name, pk_columns in {
        "users": ["id"],
        "max_chats": ["id", "user_id"],
        "kaiten_connections": ["id", "user_id"],
        "dialog_sessions": ["id", "user_id", "max_chat_binding_id"],
        "pending_commands": ["id", "user_id", "dialog_session_id"],
        "notification_settings": ["user_id"],
        "notification_history": ["id", "user_id"],
    }.items():
        for column_name in pk_columns:
            assert_type(table_name, column_name, UUID)

    text_columns = {
        "users": ["status"],
        "max_chats": ["max_user_id", "max_chat_id", "chat_type"],
        "kaiten_connections": ["api_base_url", "kaiten_user_id", "workspace_id", "status"],
        "dialog_sessions": [
            "current_board_id",
            "current_board_name",
            "current_card_id",
            "current_card_title",
            "previous_user_message",
            "previous_bot_message",
        ],
        "pending_commands": ["intent", "original_message", "state", "failure_reason"],
        "notification_settings": ["timezone"],
        "notification_history": [
            "kaiten_card_id",
            "notification_type",
            "delivery_status",
            "error_type",
        ],
    }
    for table_name, column_names in text_columns.items():
        for column_name in column_names:
            assert_type(table_name, column_name, Text)

    assert_type("max_chats", "is_primary", Boolean)
    assert_type("notification_settings", "enabled", Boolean)
    assert_type("notification_history", "due_date_time_present", Boolean)
    assert_type("kaiten_connections", "token_encryption_version", SmallInteger)
    assert_type("pending_commands", "clarification_attempts", Integer)
    assert_type("notification_settings", "due_soon_days", Integer)
    assert_type("kaiten_connections", "encrypted_api_token", BYTEA)


def test_timestamptz_columns_are_timezone_aware() -> None:
    timestamptz_columns = {
        "users": ["created_at", "updated_at"],
        "max_chats": ["created_at", "updated_at"],
        "kaiten_connections": ["last_verified_at", "created_at", "updated_at"],
        "dialog_sessions": [
            "last_card_list_at",
            "expires_at",
            "ended_at",
            "created_at",
            "updated_at",
        ],
        "pending_commands": ["expires_at", "executed_at", "created_at", "updated_at"],
        "notification_settings": ["created_at", "updated_at"],
        "notification_history": ["due_at", "sent_at", "failed_at", "created_at", "updated_at"],
    }
    for table_name, column_names in timestamptz_columns.items():
        for column_name in column_names:
            column_type = table(table_name).c[column_name].type
            assert isinstance(column_type, DateTime)
            assert column_type.timezone is True


def test_timestamp_insert_defaults_use_database_now_and_updated_at_has_orm_onupdate() -> None:
    for table_name in BUSINESS_TABLES:
        created_at = table(table_name).c.created_at
        updated_at = table(table_name).c.updated_at

        assert created_at.default is None
        assert created_at.server_default is not None
        assert created_at.onupdate is None
        assert created_at.server_onupdate is None

        assert updated_at.default is None
        assert updated_at.server_default is not None
        assert updated_at.onupdate is not None
        assert updated_at.server_onupdate is None


def test_jsonb_columns_and_default() -> None:
    assert_type("dialog_sessions", "last_card_list", JSONB)
    assert_type("pending_commands", "arguments", JSONB)
    assert_type("pending_commands", "unresolved_entity", JSONB)
    assert_type("pending_commands", "candidates", JSONB)

    default = table("pending_commands").c.arguments.server_default
    assert default is not None
    assert str(default.arg) == "jsonb_build_object('version', 1, 'payload', jsonb_build_object())"


def test_server_defaults() -> None:
    expected_defaults = {
        ("users", "status"): "'ACTIVE'",
        ("max_chats", "chat_type"): "'PRIVATE'",
        ("max_chats", "is_primary"): "true",
        ("kaiten_connections", "token_encryption_version"): "1",
        ("kaiten_connections", "status"): "'ACTIVE'",
        ("pending_commands", "state"): "'RECEIVED'",
        ("pending_commands", "clarification_attempts"): "0",
        ("notification_settings", "enabled"): "false",
        ("notification_settings", "due_soon_days"): "1",
        ("notification_settings", "timezone"): "'UTC'",
        ("notification_history", "delivery_status"): "'RESERVED'",
    }
    for (table_name, column_name), expected in expected_defaults.items():
        default = table(table_name).c[column_name].server_default
        assert default is not None
        assert str(default.arg) == expected

    for table_name in BUSINESS_TABLES:
        for column_name in ("created_at", "updated_at"):
            if column_name in table(table_name).c:
                default = table(table_name).c[column_name].server_default
                assert default is not None
                assert str(default.arg) == "now()"


def test_uuid_defaults_are_application_callables() -> None:
    for table_name in BUSINESS_TABLES - {"notification_settings"}:
        default = table(table_name).c.id.default
        assert default is not None
        assert default.is_callable
        generated = default.arg(None)
        assert isinstance(generated, uuid.UUID)
        assert table(table_name).c.id.server_default is None


def test_foreign_keys_and_ondelete_contract() -> None:
    expected = {
        ("max_chats", "user_id"): ("users.id", "RESTRICT"),
        ("kaiten_connections", "user_id"): ("users.id", "RESTRICT"),
        ("dialog_sessions", "user_id"): ("users.id", "RESTRICT"),
        ("dialog_sessions", "max_chat_binding_id"): ("max_chats.id", "SET NULL"),
        ("pending_commands", "user_id"): ("users.id", "RESTRICT"),
        ("pending_commands", "dialog_session_id"): ("dialog_sessions.id", "CASCADE"),
        ("notification_settings", "user_id"): ("users.id", "RESTRICT"),
        ("notification_history", "user_id"): ("users.id", "RESTRICT"),
    }

    for (table_name, column_name), (target, ondelete) in expected.items():
        fk = foreign_key(table_name, column_name)
        assert fk.name == f"fk_{table_name}_{column_name}_{target.split('.')[0]}"
        element = next(iter(fk.elements))
        assert str(element.target_fullname) == target
        assert element.ondelete == ondelete


def test_check_constraints_have_exact_names() -> None:
    assert check_names("users") == {"ck_users_status"}
    assert check_names("max_chats") == {"ck_max_chats_chat_type"}
    assert check_names("kaiten_connections") == {
        "ck_kaiten_connections_status",
        "ck_kaiten_connections_token_encryption_version_positive",
    }
    assert check_names("pending_commands") == {
        "ck_pending_commands_state",
        "ck_pending_commands_clarification_attempts_non_negative",
    }
    assert check_names("notification_settings") == {"ck_notification_settings_due_soon_days_range"}
    assert check_names("notification_history") == {
        "ck_notification_history_type",
        "ck_notification_history_delivery_status",
    }


def test_unique_constraints_have_exact_names() -> None:
    assert unique_constraint_names("max_chats") == {"uq_max_chats_max_chat_id"}
    assert unique_constraint_names("kaiten_connections") == {"uq_kaiten_connections_user_id"}
    assert unique_constraint_names("notification_history") == {"uq_notification_history_dedup"}


def test_index_inventory_and_no_duplicate_secondary_indexes() -> None:
    expected_indexes = {
        "users": set(),
        "max_chats": {"uq_max_chats_max_user_id_private", "uq_max_chats_user_primary"},
        "kaiten_connections": set(),
        "dialog_sessions": {
            "uq_dialog_sessions_one_active_per_user",
            "ix_dialog_sessions_max_chat_binding_id",
        },
        "pending_commands": {
            "uq_pending_commands_one_active_per_session",
            "ix_pending_commands_user_state",
            "ix_pending_commands_expires_at_active",
        },
        "notification_settings": {"ix_notification_settings_enabled_user"},
        "notification_history": set(),
    }
    for table_name, expected in expected_indexes.items():
        assert set(indexes(table_name)) == expected


def test_partial_unique_index_predicates_compile_for_postgresql() -> None:
    assert compiled_where(indexes("max_chats")["uq_max_chats_max_user_id_private"]) == (
        "chat_type = 'PRIVATE'"
    )
    assert compiled_where(indexes("max_chats")["uq_max_chats_user_primary"]) == "is_primary"
    assert compiled_where(indexes("dialog_sessions")["uq_dialog_sessions_one_active_per_user"]) == (
        "ended_at IS NULL"
    )
    assert compiled_where(
        indexes("pending_commands")["uq_pending_commands_one_active_per_session"]
    ) == ("state IN ('RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY')")
    assert compiled_where(indexes("pending_commands")["ix_pending_commands_expires_at_active"]) == (
        "state IN ('RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY') "
        "AND expires_at IS NOT NULL"
    )

    assert indexes("max_chats")["uq_max_chats_max_user_id_private"].unique is True
    assert indexes("max_chats")["uq_max_chats_user_primary"].unique is True
    assert indexes("dialog_sessions")["uq_dialog_sessions_one_active_per_user"].unique is True
    assert indexes("pending_commands")["uq_pending_commands_one_active_per_session"].unique is True


def test_notification_deadline_contract() -> None:
    history = table("notification_history")

    assert "due_at" in history.c
    assert "due_date_time_present" in history.c
    assert "due_date" not in history.c

    due_at_type = history.c.due_at.type
    assert isinstance(due_at_type, DateTime)
    assert due_at_type.timezone is True

    dedup_constraints = [
        constraint
        for constraint in history.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_notification_history_dedup"
    ]
    assert len(dedup_constraints) == 1
    assert [column.name for column in dedup_constraints[0].columns] == [
        "user_id",
        "kaiten_card_id",
        "due_at",
        "due_date_time_present",
        "notification_type",
    ]
