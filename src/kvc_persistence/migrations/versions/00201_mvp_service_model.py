"""add MVP service data model

Revision ID: 00201_mvp_service_model
Revises:
Create Date: 2026-08-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "00201_mvp_service_model"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_PENDING_STATES_SQL = (
    "state IN ('RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY')"
)


def upgrade() -> None:
    """Apply migration."""

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name=op.f("ck_users_status")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )

    op.create_table(
        "max_chats",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("max_user_id", sa.Text(), nullable=False),
        sa.Column("max_chat_id", sa.Text(), nullable=False),
        sa.Column("chat_type", sa.Text(), server_default=sa.text("'PRIVATE'"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("chat_type IN ('PRIVATE')", name=op.f("ck_max_chats_chat_type")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_max_chats_user_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_max_chats")),
        sa.UniqueConstraint("max_chat_id", name="uq_max_chats_max_chat_id"),
    )

    op.create_table(
        "kaiten_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_base_url", sa.Text(), nullable=False),
        sa.Column("kaiten_user_id", sa.Text(), nullable=True),
        sa.Column("workspace_id", sa.Text(), nullable=True),
        sa.Column("encrypted_api_token", postgresql.BYTEA(), nullable=False),
        sa.Column(
            "token_encryption_version",
            sa.SmallInteger(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED', 'NEEDS_REAUTH')",
            name=op.f("ck_kaiten_connections_status"),
        ),
        sa.CheckConstraint(
            "token_encryption_version > 0",
            name=op.f("ck_kaiten_connections_token_encryption_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_kaiten_connections_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kaiten_connections")),
        sa.UniqueConstraint("user_id", name="uq_kaiten_connections_user_id"),
    )

    op.create_table(
        "dialog_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("max_chat_binding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_board_id", sa.Text(), nullable=True),
        sa.Column("current_board_name", sa.Text(), nullable=True),
        sa.Column("current_card_id", sa.Text(), nullable=True),
        sa.Column("current_card_title", sa.Text(), nullable=True),
        sa.Column("previous_user_message", sa.Text(), nullable=True),
        sa.Column("previous_bot_message", sa.Text(), nullable=True),
        sa.Column("last_card_list", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_card_list_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["max_chat_binding_id"],
            ["max_chats.id"],
            name=op.f("fk_dialog_sessions_max_chat_binding_id_max_chats"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_dialog_sessions_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dialog_sessions")),
    )

    op.create_table(
        "pending_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dialog_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("original_message", sa.Text(), nullable=False),
        sa.Column(
            "arguments",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text(
                "jsonb_build_object('version', 1, 'payload', jsonb_build_object())"
            ),
            nullable=False,
        ),
        sa.Column("unresolved_entity", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("state", sa.Text(), server_default=sa.text("'RECEIVED'"), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "clarification_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ("
            "'RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY', "
            "'EXECUTED', 'FAILED', 'CANCELLED', 'EXPIRED'"
            ")",
            name=op.f("ck_pending_commands_state"),
        ),
        sa.CheckConstraint(
            "clarification_attempts >= 0",
            name=op.f("ck_pending_commands_clarification_attempts_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["dialog_session_id"],
            ["dialog_sessions.id"],
            name=op.f("fk_pending_commands_dialog_session_id_dialog_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_pending_commands_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pending_commands")),
    )

    op.create_table(
        "notification_settings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("due_soon_days", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("timezone", sa.Text(), server_default=sa.text("'UTC'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "due_soon_days BETWEEN 0 AND 30",
            name=op.f("ck_notification_settings_due_soon_days_range"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_settings_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_notification_settings")),
    )

    op.create_table(
        "notification_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kaiten_card_id", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date_time_present", sa.Boolean(), nullable=False),
        sa.Column("notification_type", sa.Text(), nullable=False),
        sa.Column(
            "delivery_status", sa.Text(), server_default=sa.text("'RESERVED'"), nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "notification_type IN ('DUE_SOON', 'DUE_TODAY', 'OVERDUE')",
            name=op.f("ck_notification_history_type"),
        ),
        sa.CheckConstraint(
            "delivery_status IN ('RESERVED', 'SENT', 'FAILED')",
            name=op.f("ck_notification_history_delivery_status"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_history_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_history")),
        sa.UniqueConstraint(
            "user_id",
            "kaiten_card_id",
            "due_at",
            "due_date_time_present",
            "notification_type",
            name="uq_notification_history_dedup",
        ),
    )

    op.create_index(
        "uq_max_chats_max_user_id_private",
        "max_chats",
        ["max_user_id"],
        unique=True,
        postgresql_where=sa.text("chat_type = 'PRIVATE'"),
    )
    op.create_index(
        "uq_max_chats_user_primary",
        "max_chats",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )
    op.create_index(
        "uq_dialog_sessions_one_active_per_user",
        "dialog_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        "ix_dialog_sessions_max_chat_binding_id",
        "dialog_sessions",
        ["max_chat_binding_id"],
        unique=False,
    )
    op.create_index(
        "uq_pending_commands_one_active_per_session",
        "pending_commands",
        ["dialog_session_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_PENDING_STATES_SQL),
    )
    op.create_index(
        "ix_pending_commands_user_state",
        "pending_commands",
        ["user_id", "state"],
        unique=False,
    )
    op.create_index(
        "ix_pending_commands_expires_at_active",
        "pending_commands",
        ["expires_at"],
        unique=False,
        postgresql_where=sa.text(f"{ACTIVE_PENDING_STATES_SQL} AND expires_at IS NOT NULL"),
    )
    op.create_index(
        "ix_notification_settings_enabled_user",
        "notification_settings",
        ["enabled", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Rollback migration."""

    op.drop_table("notification_history")
    op.drop_table("notification_settings")
    op.drop_table("pending_commands")
    op.drop_table("dialog_sessions")
    op.drop_table("kaiten_connections")
    op.drop_table("max_chats")
    op.drop_table("users")
