# 002-03 - Repository/query contracts implementation report

## Executive summary

Implemented the minimal async repository/query layer over the accepted seven-table PostgreSQL schema.

Repository package:

```text
src/kvc_persistence/repositories/
```

Final status:

```text
IMPLEMENTED - READY FOR 002 BRANCH ACCEPTANCE/CLOSEOUT
```

No schema migration, manual DDL, Kaiten API call, MAX API call, GigaChat/STT call, encryption implementation, scheduler, command parser, business service, or `.env` change was added.

## Baseline repository/database state

Runtime gate before implementation:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.
```

Baseline Git state:

```text
git log --oneline --decorate -5
0501ca3 (HEAD -> main) feat: add PostgreSQL persistence foundation
4e4d728 chore: bootstrap Kaiten Voice Control project

git diff --check
<no output, exit code 0>
```

Baseline worktree already contained uncommitted/untracked files from previous `002` stages. They were not reverted.

Live PostgreSQL baseline inherited from `002-02`:

```text
database: kvc_dev
app_env: development
alembic_version: 00201_mvp_service_model
business table rows: all 0
```

## Repository package architecture

Created a small infrastructure-only repository package:

```text
src/kvc_persistence/repositories/__init__.py
src/kvc_persistence/repositories/_statements.py
src/kvc_persistence/repositories/contracts.py
src/kvc_persistence/repositories/users.py
src/kvc_persistence/repositories/max_chats.py
src/kvc_persistence/repositories/kaiten_connections.py
src/kvc_persistence/repositories/dialog_sessions.py
src/kvc_persistence/repositories/pending_commands.py
src/kvc_persistence/repositories/notification_settings.py
src/kvc_persistence/repositories/notification_history.py
```

The package uses the existing SQLAlchemy ORM models and does not add ORM relationships, a generic repository framework, a service locator, or a UnitOfWork abstraction.

## Transaction ownership contract

Repository methods do not call:

```text
commit()
rollback()
```

Allowed operations used:

```text
execute
flush
refresh
```

Structural test:

```text
test_repository_sources_do_not_own_transaction_lifecycle
```

Live rollback proof:

```text
test_repository_methods_do_not_commit_and_caller_rollback_removes_rows
```

The integration test creates a row through a repository, rolls back the caller-owned transaction, opens a new session, and verifies the row is absent.

## Session contract

Every repository accepts an existing:

```text
sqlalchemy.ext.asyncio.AsyncSession
```

Constructor shape:

```python
def __init__(self, session: AsyncSession) -> None:
    self._session = session
```

Repositories do not create engines, sessionmakers, or hidden database connections.

## UserRepository API

Implemented:

```text
get_by_id(user_id)
get_by_id_for_update(user_id)
create(user_id=None, status=None)
set_status(user, status)
```

`get_by_id_for_update()` uses `SELECT ... FOR UPDATE`. `create()` uses application-side UUID when supplied or the accepted ORM UUID default when omitted.

## MaxChatRepository API

Implemented:

```text
get_by_max_chat_id(max_chat_id)
get_private_by_max_user_id(max_user_id)
get_primary_for_user(user_id)
create_private_binding(user_id, max_user_id, max_chat_id, ...)
```

The repository creates only `PRIVATE` bindings and does not auto-create users or notification settings.

## KaitenConnectionRepository API

Implemented:

```text
get_for_user(user_id)
get_for_user_for_update(user_id)
create(user_id, api_base_url, encrypted_api_token, ...)
update_connection(connection, api_base_url, encrypted_api_token, ...)
```

The repository accepts only:

```text
encrypted_api_token: bytes
```

No plaintext token field/path, encryption, decryption, key access, or token logging was added.

## DialogSessionRepository API

Implemented:

```text
get_active_for_user(user_id)
get_active_for_user_for_update(user_id)
get_or_create_active(user_id, ...)
update_context(dialog_session, **fields)
end(dialog_session, ended_at)
```

`update_context()` accepts only:

```text
max_chat_binding_id
current_board_id
current_board_name
current_card_id
current_card_title
previous_user_message
previous_bot_message
last_card_list
last_card_list_at
expires_at
```

Unsupported fields raise `PersistenceInvariantError`.

## Active-dialog locking strategy

`get_or_create_active()` uses the accepted parent-lock pattern:

```text
1. SELECT users WHERE id = :user_id FOR UPDATE
2. re-read active dialog for the user
3. return existing active dialog if present
4. insert and flush if absent
```

This serializes active dialog creation per user without advisory locks. The partial unique index remains the final database guard.

Structural tests compile the lock path and verify `FOR UPDATE`.

Live integration tests verify:

```text
same user returns same active session
ended session allows next active session
direct duplicate active dialog is rejected by PostgreSQL partial UNIQUE
```

## PendingCommandRepository API

Implemented:

```text
get_active_for_session(dialog_session_id)
get_active_for_session_for_update(dialog_session_id)
create_active(user_id, dialog_session_id, intent, original_message, ...)
update_resolution_state(command, state, ...)
update_fields(command, **fields)
```

The repository does not implement a finite-state-machine engine or business transition validation.

## Ownership invariant implementation

Required invariant:

```text
pending_commands.user_id == dialog_sessions.user_id
```

`create_active()` enforces it by:

```text
1. SELECT dialog_sessions WHERE id = :dialog_session_id FOR UPDATE
2. reject missing dialog session
3. compare dialog_session.user_id to requested user_id
4. raise PersistenceInvariantError on mismatch
5. check existing active pending command in the same transaction
6. return existing active command or insert + flush a new one
```

No composite FK or trigger was added.

Live test:

```text
test_pending_command_repository_ownership_and_active_contracts
```

## Pending-command locking strategy

Implemented lock helpers:

```text
select_dialog_session_for_update(dialog_session_id)
select_active_pending_command_for_update(dialog_session_id)
```

`create_active()` locks the dialog session row before insert. `get_active_for_session_for_update()` gives the future clarification handler a safe row-lock primitive.

The partial unique index remains the final database guard:

```text
uq_pending_commands_one_active_per_session
```

Live test:

```text
test_pending_command_partial_unique_remains_final_guard
```

## Persistence invariant exception contract

Added:

```text
PersistenceInvariantError
```

Use cases:

```text
missing parent user for concurrency-sensitive creation
missing dialog session for pending command creation
pending command ownership mismatch
unsupported dialog context fields
unsupported pending command fields
```

Messages include UUID diagnostic context where useful and do not include secrets or encrypted token values.

## NotificationSettingsRepository API

Implemented:

```text
get_for_user(user_id)
get_for_user_for_update(user_id)
get_or_create_for_user(user_id)
list_enabled()
```

`get_or_create_for_user()` locks the parent user row before insert. `list_enabled()` returns deterministic order:

```text
ORDER BY user_id
```

No hidden default settings are created by ordinary `get_for_user()`.

## NotificationHistoryRepository API

Implemented:

```text
reserve(user_id, kaiten_card_id, due_at, due_date_time_present, notification_type)
get_by_dedup_key(user_id, kaiten_card_id, due_at, due_date_time_present, notification_type)
get_by_id_for_update(user_id, notification_history_id)
mark_sent(notification, sent_at)
mark_failed(notification, failed_at, error_type)
```

`get_by_id_for_update()` is user-scoped and does not return another user's row.

## Atomic reservation implementation

`reserve()` uses PostgreSQL-native atomic reservation:

```text
INSERT INTO notification_history (...)
ON CONFLICT ON CONSTRAINT uq_notification_history_dedup DO NOTHING
RETURNING notification_history.*
```

Return contract:

```text
NotificationHistory -> reservation was created
None -> dedup duplicate already exists
```

The repository does not implement exactly-once delivery, outbox, retry scheduling, stale reservation reclaim, or MAX idempotency.

## Deadline persistence semantics

`NotificationHistoryRepository.reserve()` receives and stores normalized deadline fields literally:

```text
due_at
due_date_time_present
```

It does not parse Kaiten `due_date`, convert timezone, classify due dates, or reinterpret date-only deadlines. The `002-00c` date-only UTC-date-component rule remains future Kaiten/application-layer responsibility.

## Explicit out-of-scope business logic

Not implemented:

```text
Kaiten adapter/API calls
MAX bot/API calls
GigaChat/STT calls
command parsing
entity resolver
business state machine
notification scheduler
retry/reclaim worker
exactly-once delivery
encryption/decryption implementation
secret loading in repositories
local Kaiten content cache
schema migration
```

## Unit/structural tests

Added:

```text
tests/unit/test_repository_contracts.py
```

Coverage:

```text
repository package imports
no commit/rollback calls in repository sources
FOR UPDATE SQL compilation
active-dialog parent lock pattern
pending-command dialog lock before insert
PostgreSQL ON CONFLICT DO NOTHING reservation SQL
no plaintext Kaiten token path
```

## PostgreSQL integration tests

Added:

```text
tests/integration/test_repositories_postgresql.py
```

Safety prerequisite:

```text
KVC_APP_ENV = development
current_database() = kvc_dev
alembic_version = 00201_mvp_service_model
```

Each integration test uses synthetic UUIDs/external IDs/token bytes and a caller-owned transaction that is rolled back.

Targeted repository test result:

```text
.venv\Scripts\python.exe -m pytest tests\unit\test_repository_contracts.py tests\integration\test_repositories_postgresql.py -q
20 passed in 3.11s
```

An initial targeted run failed because the integration engine fixture was module-scoped and asyncpg connections were reused across pytest event loops on Windows. The fixture was changed to function scope; database row counts after the failed run were verified as all 0 before rerunning.

## Transaction rollback/no-hidden-commit proof

Live proof:

```text
test_repository_methods_do_not_commit_and_caller_rollback_removes_rows
```

Result:

```text
created user row through UserRepository
caller rolled back transaction
new session could not find the row
```

Structural proof:

```text
repository source scan found no .commit( or .rollback(
```

## Ownership/isolation tests

Implemented:

```text
pending command owner/session match accepted
pending command owner/session mismatch rejected with PersistenceInvariantError
notification_history.get_by_id_for_update filters by user_id
```

## Concurrency/locking tests

Implemented:

```text
FOR UPDATE SQL compiles for user parent lock
FOR UPDATE SQL compiles for active dialog lock
FOR UPDATE SQL compiles for dialog session lock before pending command insert
FOR UPDATE SQL compiles for active pending command lock
active dialog get_or_create source uses parent user lock path
pending command create source uses dialog-session lock path
dialog partial UNIQUE rejects direct duplicate active session
pending command partial UNIQUE rejects direct duplicate active command
```

No sleep-based concurrency test was added.

## Notification dedup tests

Live integration verifies:

```text
first reserve -> NotificationHistory created
same dedup key reserve -> None
different due_at -> new NotificationHistory created
mark_sent -> delivery_status SENT and sent_at set
mark_failed -> delivery_status FAILED, failed_at/error_type set
```

## Database cleanup verification

Final database check:

```json
{
  "alembic_version": "00201_mvp_service_model",
  "counts": {
    "dialog_sessions": 0,
    "kaiten_connections": 0,
    "max_chats": 0,
    "notification_history": 0,
    "notification_settings": 0,
    "pending_commands": 0,
    "users": 0
  }
}
```

## Alembic current/check result

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

No Alembic revision was added.

## Full quality gate

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.
```

```text
.venv\Scripts\python.exe -m pytest
61 passed in 3.99s
```

```text
.venv\Scripts\python.exe -m pytest -W error
61 passed in 3.96s
```

```text
.venv\Scripts\python.exe -m ruff format --check .
71 files already formatted
```

```text
.venv\Scripts\python.exe -m ruff check .
All checks passed!
```

```text
.venv\Scripts\python.exe -m mypy src
Success: no issues found in 33 source files
```

```text
git diff --check
<no output, exit code 0>
```

## Changed files

Production code:

```text
src/kvc_persistence/repositories/__init__.py
src/kvc_persistence/repositories/_statements.py
src/kvc_persistence/repositories/contracts.py
src/kvc_persistence/repositories/users.py
src/kvc_persistence/repositories/max_chats.py
src/kvc_persistence/repositories/kaiten_connections.py
src/kvc_persistence/repositories/dialog_sessions.py
src/kvc_persistence/repositories/pending_commands.py
src/kvc_persistence/repositories/notification_settings.py
src/kvc_persistence/repositories/notification_history.py
```

Repositories:

```text
UserRepository
MaxChatRepository
KaitenConnectionRepository
DialogSessionRepository
PendingCommandRepository
NotificationSettingsRepository
NotificationHistoryRepository
PersistenceInvariantError
```

Tests:

```text
tests/unit/test_imports.py
tests/unit/test_repository_contracts.py
tests/integration/test_repositories_postgresql.py
```

Alembic:

```text
none
```

Configuration:

```text
none
```

Documentation:

```text
none
```

Reports:

```text
codex/reports/002_03_repository_query_contracts_implementation_report.md
```

Database state:

```text
alembic_version = 00201_mvp_service_model
synthetic repository test rows = 0
```

Other:

```text
none
```

## Git status and diff stat

Final `git status --short` includes prior uncommitted/untracked `002` files plus this stage's repository/test/report files:

```text
 M .gitignore
 M src/kvc_persistence/migrations/env.py
 M tests/unit/test_alembic_foundation.py
 M tests/unit/test_imports.py
 M tests/unit/test_persistence.py
?? codex/prompts/002_00_mvp_service_data_model_audit_prompt.md
?? codex/prompts/002_00a_mvp_service_data_model_final_specification_prompt.md
?? codex/prompts/002_00b_kaiten_deadline_notification_semantics_correction_prompt.md
?? codex/prompts/002_00c_live_kaiten_deadline_representation_acceptance_probe_prompt.md
?? codex/prompts/002_01_mvp_service_data_model_implementation_prompt.md
?? codex/prompts/002_01a_python312_persistence_clean_gate_prompt.md
?? codex/prompts/002_02_live_postgresql_persistence_acceptance_prompt.md
?? codex/prompts/002_03_repository_query_contracts_implementation_prompt.md
?? codex/reports/002_00_mvp_service_data_model_audit_report.md
?? codex/reports/002_00a_mvp_service_data_model_final_specification.md
?? codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
?? codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
?? codex/reports/002_01_mvp_service_data_model_implementation_report.md
?? codex/reports/002_01a_python312_persistence_clean_gate_report.md
?? codex/reports/002_02_live_postgresql_persistence_acceptance_report.md
?? src/kvc_persistence/migrations/versions/00201_mvp_service_model.py
?? src/kvc_persistence/models.py
?? src/kvc_persistence/repositories/
?? tests/integration/
?? tests/unit/test_persistence_models.py
?? tests/unit/test_repository_contracts.py
```

Tracked diff stat:

```text
.gitignore                            |  2 +-
src/kvc_persistence/migrations/env.py | 18 ++++++++++++++++++
tests/unit/test_alembic_foundation.py | 29 ++++++++++++++++++++++++++---
tests/unit/test_imports.py            |  2 ++
tests/unit/test_persistence.py        | 14 ++++++++++++--
5 files changed, 59 insertions(+), 6 deletions(-)
```

`git diff --stat` does not include untracked repository/model/migration/test/report files.

## Deferred application/business work

Deferred to later stages:

```text
application services and transaction orchestration
Kaiten adapter and command mutation flow
MAX bot handlers and notification sending
token encryption/decryption service
business command state-machine validation
deadline parsing/classification using 002-00c semantics
notification polling/retry/reclaim worker
cleanup/retention jobs
```

## Final status

```text
IMPLEMENTED - READY FOR 002 BRANCH ACCEPTANCE/CLOSEOUT
```
