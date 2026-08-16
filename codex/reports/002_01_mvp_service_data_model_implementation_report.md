# 002-01 - MVP service data model implementation report

## Executive summary

Implemented the frozen MVP persistence contract as SQLAlchemy 2.x typed ORM metadata and one initial Alembic revision.

Final status: `IMPLEMENTED - READY FOR 002-02 LIVE POSTGRESQL ACCEPTANCE`.

Important environment note: the project `.venv` launcher is broken because it points to a missing Python 3.12 executable. The required `.venv\Scripts\python.exe -m ...` gates all fail before project code runs. Code-level gates were therefore also executed in an isolated temporary Python 3.14 fallback environment plus the project standalone Ruff executable.

No live PostgreSQL schema migration, downgrade, manual DDL, Kaiten mutation, MAX call, secret printing, repository layer, service layer, encryption implementation, worker logic, or seed data was performed.

## Contract precedence

Applied contract priority exactly as specified:

1. `002-00c` for live-verified deadline representation.
2. `002-00b` for notification deadline and dedup corrections.
3. `002-00a` for the frozen seven-table schema.
4. `002-00` for background rationale.

`notification_history.due_date DATE` was not implemented. The final implementation uses:

```text
notification_history.due_at TIMESTAMPTZ NOT NULL
notification_history.due_date_time_present BOOLEAN NOT NULL
```

## Baseline repository state

Baseline command results before implementation:

```text
git log --oneline --decorate -5
0501ca3 (HEAD -> main) feat: add PostgreSQL persistence foundation
4e4d728 chore: bootstrap Kaiten Voice Control project

git diff --check
<no output, exit code 0>
```

Baseline `git status --short` contained only untracked codex prompts/reports from the previous 002 stages and the current prompt file. Existing migration directory contained only `.gitkeep`.

## Existing persistence/Alembic foundation

- Existing SQLAlchemy Base: `src/kvc_persistence/base.py`.
- Existing MetaData: `Base.metadata`.
- Naming convention preserved:
  - `ix_%(column_0_label)s`
  - `uq_%(table_name)s_%(column_0_name)s`
  - `ck_%(table_name)s_%(constraint_name)s`
  - `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s`
  - `pk_%(table_name)s`
- Engine/session modules preserved:
  - `src/kvc_persistence/engine.py`
  - `src/kvc_persistence/session.py`
  - `src/kvc_persistence/health.py`
- Alembic env preserved and extended to import the model registry before assigning `target_metadata = Base.metadata`.
- No second `DeclarativeBase` or `MetaData` was created.

## Model package/files

Created:

```text
src/kvc_persistence/models.py
```

The module defines the seven ORM classes using typed SQLAlchemy 2.x declarative style:

```text
User
MaxChat
KaitenConnection
DialogSession
PendingCommand
NotificationSetting
NotificationHistory
```

No ORM relationships were added. Foreign key constraints remain the referential source of truth.

## Final seven-table inventory

Exactly these KVC-owned business tables are registered in `Base.metadata`:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

No Kaiten mirror tables were added:

```text
boards
spaces
columns
cards
comments
attachments
card_states
kaiten_due_dates
```

## Column/type/nullability/default inventory

Implemented PostgreSQL physical type mappings:

```text
UUID        -> postgresql.UUID(as_uuid=True)
TEXT        -> sa.Text
BOOLEAN     -> sa.Boolean
SMALLINT    -> sa.SmallInteger
INTEGER     -> sa.Integer
BYTEA       -> postgresql.BYTEA
TIMESTAMPTZ -> sa.DateTime(timezone=True)
JSONB       -> postgresql.JSONB
```

Finite states are `TEXT + CHECK`. PostgreSQL ENUM was not used.

Accepted server defaults implemented:

```text
users.status = 'ACTIVE'
max_chats.chat_type = 'PRIVATE'
max_chats.is_primary = true
kaiten_connections.token_encryption_version = 1
kaiten_connections.status = 'ACTIVE'
pending_commands.arguments = jsonb_build_object('version', 1, 'payload', jsonb_build_object())
pending_commands.state = 'RECEIVED'
pending_commands.clarification_attempts = 0
notification_settings.enabled = false
notification_settings.due_soon_days = 1
notification_settings.timezone = 'UTC'
notification_history.delivery_status = 'RESERVED'
created_at = now()
updated_at = now()
```

UUID PK columns have application callable defaults and no server default.

## PK/FK/ON DELETE inventory

Primary keys:

```text
pk_users: users.id
pk_max_chats: max_chats.id
pk_kaiten_connections: kaiten_connections.id
pk_dialog_sessions: dialog_sessions.id
pk_pending_commands: pending_commands.id
pk_notification_settings: notification_settings.user_id
pk_notification_history: notification_history.id
```

Foreign keys:

```text
fk_max_chats_user_id_users: users.id ON DELETE RESTRICT
fk_kaiten_connections_user_id_users: users.id ON DELETE RESTRICT
fk_dialog_sessions_user_id_users: users.id ON DELETE RESTRICT
fk_dialog_sessions_max_chat_binding_id_max_chats: max_chats.id ON DELETE SET NULL
fk_pending_commands_user_id_users: users.id ON DELETE RESTRICT
fk_pending_commands_dialog_session_id_dialog_sessions: dialog_sessions.id ON DELETE CASCADE
fk_notification_settings_user_id_users: users.id ON DELETE RESTRICT
fk_notification_history_user_id_users: users.id ON DELETE RESTRICT
```

## CHECK inventory

Implemented exact CHECK names:

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

Semantic constraint names were used in ORM definitions so the existing naming convention does not create double prefixes.

## UNIQUE/partial UNIQUE inventory

Implemented ordinary UNIQUE constraints:

```text
uq_max_chats_max_chat_id
uq_kaiten_connections_user_id
uq_notification_history_dedup
```

Implemented PostgreSQL-native partial UNIQUE indexes:

```text
uq_max_chats_max_user_id_private
  UNIQUE (max_user_id) WHERE chat_type = 'PRIVATE'

uq_max_chats_user_primary
  UNIQUE (user_id) WHERE is_primary

uq_dialog_sessions_one_active_per_user
  UNIQUE (user_id) WHERE ended_at IS NULL

uq_pending_commands_one_active_per_session
  UNIQUE (dialog_session_id)
  WHERE state IN ('RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY')
```

## Secondary index inventory

Implemented only accepted secondary indexes:

```text
ix_dialog_sessions_max_chat_binding_id
ix_pending_commands_user_state
ix_pending_commands_expires_at_active
ix_notification_settings_enabled_user
```

No secondary index was added to `notification_history`.

## No-duplicate-index review

No duplicate secondary indexes were added for:

```text
max_chats.max_chat_id
max_chats.max_user_id private lookup
max_chats user primary lookup
kaiten_connections.user_id
notification_history dedup tuple
```

Structural tests assert the exact index inventory per table.

## JSONB mapping review

Implemented JSONB fields:

```text
dialog_sessions.last_card_list
pending_commands.arguments
pending_commands.unresolved_entity
pending_commands.candidates
```

No JSONB GIN indexes or normalized Kaiten snapshot tables were added.

`pending_commands.arguments` uses a real PostgreSQL JSONB expression default:

```text
jsonb_build_object('version', 1, 'payload', jsonb_build_object())
```

This avoids SQLAlchemy `sa.text()` bind-marker ambiguity around JSON text containing `:1`.

## Secret field handling

`kaiten_connections.encrypted_api_token` is stored as `BYTEA`.

No plaintext token field, encryption implementation, secret logging, real token fixture, `.env` change, or secret-bearing migration payload was added.

## UUID generation

All surrogate UUID primary keys use application-side `uuid.uuid4` defaults:

```text
users.id
max_chats.id
kaiten_connections.id
dialog_sessions.id
pending_commands.id
notification_history.id
```

`notification_settings.user_id` is both PK and FK and is not generated independently.

No PostgreSQL UUID extension, `gen_random_uuid()`, `uuid-ossp`, server-side UUID generation, or integer identity PK was added.

## Timestamp/TIMESTAMPTZ contract

All instant fields use `DateTime(timezone=True)` / `TIMESTAMPTZ`.

`created_at` and `updated_at` have server default `now()`. ORM models also use timezone-aware Python defaults and `updated_at` has application-side `onupdate`.

No DB trigger was added.

## Final notification deadline implementation

`notification_history` implements the live-verified 002-00c contract:

```text
due_at TIMESTAMPTZ NOT NULL
due_date_time_present BOOLEAN NOT NULL
uq_notification_history_dedup:
  UNIQUE (user_id, kaiten_card_id, due_at, due_date_time_present, notification_type)
```

`due_date` is absent from ORM metadata and migration text.

The implementation does not add notification classification logic. The 002-00c rule remains deferred to application logic:

```text
When due_date_time_present = false, recover the selected calendar date
from the UTC date component of due_at.
```

## PendingCommand ownership invariant scope

Schema representation: implemented with both ordinary FKs:

```text
pending_commands.user_id -> users.id
pending_commands.dialog_session_id -> dialog_sessions.id
```

Runtime cross-row enforcement:

```text
deferred to 002-03
```

No composite FK, DB trigger, repository layer, service layer, or global ORM hook was added.

## Alembic revision

Created:

```text
src/kvc_persistence/migrations/versions/00201_mvp_service_model.py
```

Revision metadata:

```text
revision = 00201_mvp_service_model
message = add MVP service data model
down_revision = None
```

Upgrade creates the seven business tables in contract order, then creates accepted partial UNIQUE and secondary indexes.

Downgrade drops the seven business tables in reverse dependency order:

```text
notification_history
notification_settings
pending_commands
dialog_sessions
kaiten_connections
max_chats
users
```

The migration does not create extensions, ENUMs, seed data, manual `alembic_version` rows, unrelated DDL, or live DB changes.

## Model/migration parity review

Parity is covered by structural tests for:

```text
tables
columns
types
nullability
PK
FK targets
ON DELETE
CHECK names
UNIQUE names
partial UNIQUE indexes
secondary indexes
server defaults
deadline fields
JSONB columns
UUID defaults
absence of DATE/ENUM/extension in migration
```

Offline SQL render was inspected. It contains `TIMESTAMP WITH TIME ZONE`, `JSONB`, `BYTEA`, partial indexes, and the final `notification_history` dedup tuple.

## Alembic heads/history

Required `.venv` commands failed before code execution:

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini heads
No Python at '"C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe'

.venv\Scripts\python.exe -m alembic -c alembic.ini history
No Python at '"C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe'
```

Fallback temp Python 3.14 results:

```text
python -m alembic -c alembic.ini heads
00201_mvp_service_model (head)

python -m alembic -c alembic.ini history
<base> -> 00201_mvp_service_model (head), add MVP service data model
```

## Offline migration verification

Required `.venv` command failed before code execution for the same missing Python 3.12 launcher.

Fallback temp Python 3.14:

```text
python -m alembic -c alembic.ini upgrade head --sql
exit code 0
```

Key rendered SQL facts:

```text
CREATE TABLE users
CREATE TABLE max_chats
CREATE TABLE kaiten_connections
CREATE TABLE dialog_sessions
CREATE TABLE pending_commands
CREATE TABLE notification_settings
CREATE TABLE notification_history
arguments JSONB DEFAULT jsonb_build_object('version', 1, 'payload', jsonb_build_object()) NOT NULL
due_at TIMESTAMP WITH TIME ZONE NOT NULL
due_date_time_present BOOLEAN NOT NULL
CREATE UNIQUE INDEX uq_max_chats_max_user_id_private ... WHERE chat_type = 'PRIVATE'
CREATE UNIQUE INDEX uq_max_chats_user_primary ... WHERE is_primary
CREATE UNIQUE INDEX uq_dialog_sessions_one_active_per_user ... WHERE ended_at IS NULL
CREATE UNIQUE INDEX uq_pending_commands_one_active_per_session ... WHERE state IN (...)
CREATE INDEX ix_pending_commands_expires_at_active ... AND expires_at IS NOT NULL
```

## Tests added/updated

Added:

```text
tests/unit/test_persistence_models.py
```

Updated:

```text
tests/unit/test_persistence.py
tests/unit/test_imports.py
tests/unit/test_alembic_foundation.py
```

Targeted fallback result:

```text
pytest tests\unit\test_persistence_models.py tests\unit\test_alembic_foundation.py -q
17 passed
```

## Full quality gate

Required project `.venv` results:

```text
.venv\Scripts\python.exe --version
No Python at '"C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe'

.venv\Scripts\python.exe -m pip check
No Python at '"C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe'

.venv\Scripts\python.exe -m pytest
No Python at '"C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe'

.venv\Scripts\python.exe -m pytest -W error
No Python at '"C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe'

.venv\Scripts\python.exe -m ruff format --check .
No Python at '"C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe'

.venv\Scripts\python.exe -m ruff check .
No Python at '"C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe'

.venv\Scripts\python.exe -m mypy src
No Python at '"C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe'
```

Project standalone Ruff executable:

```text
.venv\Scripts\ruff.exe format --check .
52 files already formatted

.venv\Scripts\ruff.exe check .
All checks passed!
```

Fallback temp Python 3.14 environment:

```text
python --version
Python 3.14.3

python -m pip check
No broken requirements found.

python -m pytest
40 passed

python -m pytest -W error
40 passed

python -m mypy src
Success: no issues found in 23 source files
```

Git checks:

```text
git diff --check
<no output, exit code 0>

git diff --stat
src/kvc_persistence/migrations/env.py | 18 ++++++++++++++++++
tests/unit/test_alembic_foundation.py | 29 ++++++++++++++++++++++++++---
tests/unit/test_imports.py            |  1 +
tests/unit/test_persistence.py        | 14 ++++++++++++--
4 files changed, 57 insertions(+), 5 deletions(-)
```

`git diff --stat` lists only tracked modifications. New untracked files are listed in the changed-files section below.

## Changed files

Production code:

```text
src/kvc_persistence/models.py
```

Alembic:

```text
src/kvc_persistence/migrations/versions/00201_mvp_service_model.py
```

Tests:

```text
tests/unit/test_persistence.py
tests/unit/test_imports.py
tests/unit/test_alembic_foundation.py
tests/unit/test_persistence_models.py
```

Configuration:

```text
src/kvc_persistence/migrations/env.py
```

Documentation:

```text
none
```

Reports:

```text
codex/reports/002_01_mvp_service_data_model_implementation_report.md
```

Other:

```text
codex/prompts/002_01_mvp_service_data_model_implementation_prompt.md
  Ruff-formatted one Python snippet in the prompt markdown.
```

`.env` remained unchanged.

## Explicit out of scope

Not implemented in `002-01`:

```text
live PostgreSQL upgrade/downgrade
manual schema inspection against live PostgreSQL
Kaiten/MAX integrations
Kaiten mutations
LLM/business services
repositories
token encryption/decryption implementation
PendingCommand runtime state machine
notification classification
worker polling/retries/outbox
seed data
API/CLI admin commands
```

## Risks/deferred items

- `002-02` must run live PostgreSQL upgrade/downgrade and inspect the physical schema.
- `002-03` must enforce `pending_commands.user_id == dialog_sessions.user_id` at repository/application transaction boundary.
- `002-03` or later must implement encrypted token handling without plaintext storage.
- Notification timezone/date classification remains application logic and must follow 002-00c.
- The project `.venv` must be repaired or recreated with a valid CPython 3.12 runtime before relying on the prescribed local quality gate commands.

## Stage status

```text
IMPLEMENTED - READY FOR 002-02 LIVE POSTGRESQL ACCEPTANCE
```
