# 002-02 - Live PostgreSQL persistence acceptance report

## Executive summary

Executed live PostgreSQL acceptance for Alembic revision:

```text
00201_mvp_service_model
```

Runtime used for every Python command:

```text
.venv\Scripts\python.exe
Python 3.12.9
```

Final database state:

```text
alembic_version = 00201_mvp_service_model
business tables = 7
synthetic DML rows = 0
```

Final status:

```text
ACCEPTED LIVE POSTGRESQL PERSISTENCE - READY FOR 002-03
```

No production code, migration code, tests, `.env`, Kaiten integration, MAX integration, or manual PostgreSQL DDL was changed during this stage.

## Safety gate

Connection was verified through application settings without printing secrets.

Safe URL fields:

```text
app_env: development
drivername: postgresql+asyncpg
host: 127.0.0.1
port: 5432
database: kvc_dev
username: kvc_user
```

Database diagnostics:

```text
PostgreSQL 18.6 on x86_64-windows, compiled by msvc-19.44.35228, 64-bit
current_database: kvc_dev
current_user: kvc_user
current_schema: public
timezone: Europe/Kaliningrad
select_1: 1
```

Pre-migration inventory:

```text
public_tables: alembic_version
alembic_rows: []
existing_business_tables: []
```

The configured target was accepted as a safe local development database.

## Pre-upgrade Alembic state

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini heads
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini history
<base> -> 00201_mvp_service_model (head), add MVP service data model

.venv\Scripts\python.exe -m alembic -c alembic.ini current
<no output>
```

## First live upgrade

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
<no output, exit code 0>

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)
```

`alembic_version` after upgrade:

```text
00201_mvp_service_model
```

## Physical table inventory

Tables after live upgrade:

```text
alembic_version
dialog_sessions
kaiten_connections
max_chats
notification_history
notification_settings
pending_commands
users
```

KVC business table inventory:

```text
dialog_sessions
kaiten_connections
max_chats
notification_history
notification_settings
pending_commands
users
```

Business table count:

```text
7
```

No Kaiten mirror/content tables were created.

## Column inventory

`users`:

```text
id uuid NOT NULL
status text NOT NULL DEFAULT 'ACTIVE'::text
created_at timestamptz NOT NULL DEFAULT now()
updated_at timestamptz NOT NULL DEFAULT now()
```

`max_chats`:

```text
id uuid NOT NULL
user_id uuid NOT NULL
max_user_id text NOT NULL
max_chat_id text NOT NULL
chat_type text NOT NULL DEFAULT 'PRIVATE'::text
is_primary bool NOT NULL DEFAULT true
created_at timestamptz NOT NULL DEFAULT now()
updated_at timestamptz NOT NULL DEFAULT now()
```

`kaiten_connections`:

```text
id uuid NOT NULL
user_id uuid NOT NULL
api_base_url text NOT NULL
kaiten_user_id text NULL
workspace_id text NULL
encrypted_api_token bytea NOT NULL
token_encryption_version int2 NOT NULL DEFAULT 1
status text NOT NULL DEFAULT 'ACTIVE'::text
last_verified_at timestamptz NULL
created_at timestamptz NOT NULL DEFAULT now()
updated_at timestamptz NOT NULL DEFAULT now()
```

`dialog_sessions`:

```text
id uuid NOT NULL
user_id uuid NOT NULL
max_chat_binding_id uuid NULL
current_board_id text NULL
current_board_name text NULL
current_card_id text NULL
current_card_title text NULL
previous_user_message text NULL
previous_bot_message text NULL
last_card_list jsonb NULL
last_card_list_at timestamptz NULL
expires_at timestamptz NULL
ended_at timestamptz NULL
created_at timestamptz NOT NULL DEFAULT now()
updated_at timestamptz NOT NULL DEFAULT now()
```

`pending_commands`:

```text
id uuid NOT NULL
user_id uuid NOT NULL
dialog_session_id uuid NOT NULL
intent text NOT NULL
original_message text NOT NULL
arguments jsonb NOT NULL DEFAULT jsonb_build_object('version', 1, 'payload', jsonb_build_object())
unresolved_entity jsonb NULL
candidates jsonb NULL
state text NOT NULL DEFAULT 'RECEIVED'::text
failure_reason text NULL
clarification_attempts int4 NOT NULL DEFAULT 0
expires_at timestamptz NULL
executed_at timestamptz NULL
created_at timestamptz NOT NULL DEFAULT now()
updated_at timestamptz NOT NULL DEFAULT now()
```

`notification_settings`:

```text
user_id uuid NOT NULL
enabled bool NOT NULL DEFAULT false
due_soon_days int4 NOT NULL DEFAULT 1
timezone text NOT NULL DEFAULT 'UTC'::text
created_at timestamptz NOT NULL DEFAULT now()
updated_at timestamptz NOT NULL DEFAULT now()
```

`notification_history`:

```text
id uuid NOT NULL
user_id uuid NOT NULL
kaiten_card_id text NOT NULL
due_at timestamptz NOT NULL
due_date_time_present bool NOT NULL
notification_type text NOT NULL
delivery_status text NOT NULL DEFAULT 'RESERVED'::text
sent_at timestamptz NULL
failed_at timestamptz NULL
error_type text NULL
created_at timestamptz NOT NULL DEFAULT now()
updated_at timestamptz NOT NULL DEFAULT now()
```

## Deadline contract

Confirmed present:

```text
notification_history.due_at timestamptz NOT NULL
notification_history.due_date_time_present bool NOT NULL
uq_notification_history_dedup:
  user_id, kaiten_card_id, due_at, due_date_time_present, notification_type
```

Confirmed absent:

```text
notification_history.due_date
due_date DATE
```

## Constraints and indexes

Primary keys:

```text
pk_users
pk_max_chats
pk_kaiten_connections
pk_dialog_sessions
pk_pending_commands
pk_notification_settings
pk_notification_history
```

Foreign keys and delete actions:

```text
fk_max_chats_user_id_users: ON DELETE RESTRICT
fk_kaiten_connections_user_id_users: ON DELETE RESTRICT
fk_dialog_sessions_user_id_users: ON DELETE RESTRICT
fk_dialog_sessions_max_chat_binding_id_max_chats: ON DELETE SET NULL
fk_pending_commands_dialog_session_id_dialog_sessions: ON DELETE CASCADE
fk_pending_commands_user_id_users: ON DELETE RESTRICT
fk_notification_settings_user_id_users: ON DELETE RESTRICT
fk_notification_history_user_id_users: ON DELETE RESTRICT
```

Check constraints:

```text
ck_users_status
ck_max_chats_chat_type
ck_kaiten_connections_status
ck_kaiten_connections_token_encryption_version_positive
ck_pending_commands_state
ck_pending_commands_clarification_attempts_non_negative
ck_notification_settings_due_soon_days_range
ck_notification_history_type
ck_notification_history_delivery_status
```

Unique constraints:

```text
uq_max_chats_max_chat_id
uq_kaiten_connections_user_id
uq_notification_history_dedup
```

Partial unique indexes:

```text
uq_max_chats_max_user_id_private WHERE chat_type = 'PRIVATE'
uq_max_chats_user_primary WHERE is_primary
uq_dialog_sessions_one_active_per_user WHERE ended_at IS NULL
uq_pending_commands_one_active_per_session WHERE state IN ('RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY')
```

Secondary indexes:

```text
ix_dialog_sessions_max_chat_binding_id
ix_pending_commands_user_state
ix_pending_commands_expires_at_active
ix_notification_settings_enabled_user
```

Duplicate index definitions:

```text
none
```

Public enum types:

```text
none
```

Extensions:

```text
plpgsql
```

No project-specific PostgreSQL extension or enum was created.

## DML smoke test

All smoke rows used synthetic UUIDs and synthetic external identifiers only. The DML smoke ran inside a transaction and ended with rollback.

Constraint rejection checks:

```text
users.status invalid: rejected by ck_users_status
kaiten token version 0: rejected by ck_kaiten_connections_token_encryption_version_positive
pending clarification negative: rejected by ck_pending_commands_clarification_attempts_non_negative
notification due soon days 31: rejected by ck_notification_settings_due_soon_days_range
notification type invalid: rejected by ck_notification_history_type
```

Default checks:

```text
users.status = ACTIVE
users.created_at set by DB
users.updated_at set by DB
notification_settings.enabled = false
notification_settings.due_soon_days = 1
notification_settings.timezone = UTC
pending_commands.arguments = {"version": 1, "payload": {}}
pending_commands.state = RECEIVED
pending_commands.clarification_attempts = 0
notification_history.delivery_status = RESERVED
```

Unique and partial unique behavior:

```text
active dialog partial unique duplicate rejected
new dialog after ended_at allowed
active pending command partial unique duplicate rejected
new pending command after terminal state allowed
max_chat_id duplicate rejected
private max_user_id duplicate rejected
primary chat duplicate rejected
notification dedup duplicate rejected
notification with different due_at allowed
```

Foreign-key behavior:

```text
dialog_sessions.max_chat_binding_id set to NULL when max_chats row deleted
pending_commands rows cascaded when dialog_sessions row deleted
users row delete rejected while restricted dependents exist
```

Post-rollback counts:

```text
dialog_sessions: 0
kaiten_connections: 0
max_chats: 0
notification_history: 0
notification_settings: 0
pending_commands: 0
users: 0
```

## Downgrade and second upgrade

Schema fingerprint after first upgrade:

```text
11a9d3aed3d032c6ab65b5eaf816ec02d0abd65285f3323f22bd1889dce13eb3
```

Downgrade command:

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini downgrade base
<no output, exit code 0>
```

Post-downgrade state:

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini current
<no output>

public_tables:
  alembic_version
business_tables: []
alembic_rows: []
```

Second upgrade command:

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
<no output, exit code 0>
```

Schema fingerprint after second upgrade:

```text
11a9d3aed3d032c6ab65b5eaf816ec02d0abd65285f3323f22bd1889dce13eb3
```

Fingerprint comparison:

```text
match: true
```

Final live state after round-trip:

```text
alembic_version: 00201_mvp_service_model
business_table_count: 7
business table rows: all 0
```

## Alembic autogenerate check

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

## Final quality gate

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.
```

```text
.venv\Scripts\python.exe -m pytest
41 passed in 2.17s
```

```text
.venv\Scripts\python.exe -m pytest -W error
41 passed in 2.17s
```

```text
.venv\Scripts\python.exe -m ruff format --check .
57 files already formatted
```

```text
.venv\Scripts\python.exe -m ruff check .
All checks passed!
```

```text
.venv\Scripts\python.exe -m mypy src
Success: no issues found in 23 source files
```

```text
git diff --check
<no output, exit code 0>

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)
```

## Changed files

Changed by this stage:

```text
codex/reports/002_02_live_postgresql_persistence_acceptance_report.md
```

Production code:

```text
none
```

Alembic migration files:

```text
none
```

Tests:

```text
none
```

Configuration:

```text
none
```

Database:

```text
Upgraded live dev PostgreSQL to 00201_mvp_service_model.
Synthetic DML was rolled back.
Final business table row counts are all 0.
```

Worktree context at the end of this stage still contains prior uncommitted/untracked files from `002-00` through `002-01a`, including the persistence implementation files. Those files were not reverted or modified by `002-02`.

## Notes and risks

- PostgreSQL 18 reports internal NOT NULL constraints in `pg_constraint` as `contype = 'n'`; these were excluded from named project constraint fingerprinting.
- The first DML smoke attempt failed because asyncpg rejected a multi-statement prepared command. It made no persistent data changes. The corrected DML smoke used single statements and completed successfully in a rolled-back transaction.
- No manual DDL was executed. Schema changes were performed only through Alembic upgrade/downgrade commands.
- Secrets were not printed.

## Stage status

```text
ACCEPTED LIVE POSTGRESQL PERSISTENCE - READY FOR 002-03
```
