# 003-02 - Identity onboarding service implementation report

## 1. Executive summary

Implemented `IdentityService` for the single branch `003-02` business boundary:

```text
PRIVATE MAX identity -> KVC user identity
```

Implemented outcomes:

```text
resolve existing identity
safe rotate existing MAX chat binding
atomically onboard new KVC user
```

Implemented error outcomes:

```text
IdentityConflict
PersistenceConflict
```

No Kaiten credential lifecycle, TokenCipher adapter, crypto/key loading, MAX transport, command processing, dialog workflow, notification delivery, schema migration, dependency change, or provider call was added.

Final status:

```text
IMPLEMENTED - READY FOR 003-03 TOKEN CIPHER ADAPTER
```

## 2. Frozen sources and precedence

Sources used:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/002_03_repository_query_contracts_implementation_report.md
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

Precedence:

```text
003-00a final specification
003-01 accepted implementation contract
002-04 accepted persistence closeout
002-03 repository implementation
```

The prompt file requested by the user was not present under `codex/prompts/`; the only matching file was present as:

```text
codex/reports/003_02_identity_onboarding_service_implementation_prompt.md
```

That file was used as the current task prompt and left uncommitted as a `003-02` input artifact.

## 3. Initial Git/worktree state

Before checkpoint:

```text
git branch --show-current
003-application-service-user-onboarding
```

Status:

```text
 M src/kvc_application/__init__.py
?? codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
?? codex/prompts/003_00a_application_service_user_onboarding_final_specification_prompt.md
?? codex/prompts/003_01_application_service_contracts_implementation_prompt.md
?? codex/reports/003_00_application_service_user_onboarding_audit_report.md
?? codex/reports/003_00a_application_service_user_onboarding_final_specification.md
?? codex/reports/003_01_application_service_contracts_implementation_report.md
?? codex/reports/003_02_identity_onboarding_service_implementation_prompt.md
?? src/kvc_application/dto.py
?? src/kvc_application/errors.py
?? src/kvc_application/ports.py
?? tests/unit/test_application_dto_contracts.py
?? tests/unit/test_application_error_contracts.py
?? tests/unit/test_application_port_contracts.py
```

Ignored local artifacts remained untracked:

```text
.coverage
.env
.mypy_cache/
.pytest_cache/
.python312/
.ruff_cache/
.venv/
__pycache__/
src/kaiten_voice_control.egg-info/
```

## 4. Pre-checkpoint quality gate

Before staging `003-01`:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
94 passed in 4.32s

.venv\Scripts\python.exe -m pytest -W error
94 passed in 4.50s

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 36 source files

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.

git diff --check
<no output, exit code 0>
```

`ruff format --check .` initially failed only on Python snippets inside the current `003-02` prompt artifact. Those snippets were minimally reformatted. Final pre-checkpoint result:

```text
.venv\Scripts\python.exe -m ruff format --check .
86 files already formatted
```

## 5. Accepted 003-01 staged inventory

Staged files for the checkpoint:

```text
A codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
A codex/prompts/003_00a_application_service_user_onboarding_final_specification_prompt.md
A codex/prompts/003_01_application_service_contracts_implementation_prompt.md
A codex/reports/003_00_application_service_user_onboarding_audit_report.md
A codex/reports/003_00a_application_service_user_onboarding_final_specification.md
A codex/reports/003_01_application_service_contracts_implementation_report.md
M src/kvc_application/__init__.py
A src/kvc_application/dto.py
A src/kvc_application/errors.py
A src/kvc_application/ports.py
A tests/unit/test_application_dto_contracts.py
A tests/unit/test_application_error_contracts.py
A tests/unit/test_application_port_contracts.py
```

The current `003-02` prompt artifact was not staged.

Staged check:

```text
git diff --cached --check
<no output, exit code 0>
```

Staged diff:

```text
13 files changed, 8034 insertions(+), 1 deletion(-)
```

## 6. Checkpoint secret audit

Secret scan of staged `003-00/00a/01` source, tests, prompts, and reports found no real secrets.

Matches were limited to:

```text
normative references to forbidden secret material
field names such as encrypted_api_token
synthetic fake test values
```

No real Kaiten token, Authorization header value, Bearer token value, encryption key, database password, or private provider data was staged.

## 7. Checkpoint commit SHA/message

Created checkpoint commit:

```text
f99b2c8 feat: add application service contracts
```

Post-checkpoint log:

```text
f99b2c8 (HEAD -> 003-application-service-user-onboarding) feat: add application service contracts
568a0bb (002-mvp-service-data-model) docs: close MVP service data model branch
4abdb91 feat: add persistence repository contracts
9cd4f91 feat: add MVP service persistence model
0501ca3 (main) feat: add PostgreSQL persistence foundation
```

## 8. Post-checkpoint branch/worktree state

After checkpoint:

```text
?? codex/reports/003_02_identity_onboarding_service_implementation_prompt.md
```

`git diff --check`:

```text
<no output, exit code 0>
```

## 9. 003-02 baseline gate

Before `003-02` source changes:

```text
git branch --show-current
003-application-service-user-onboarding

.venv\Scripts\python.exe -m pytest
94 passed in 4.56s

.venv\Scripts\python.exe -m pytest -W error
94 passed in 4.07s

.venv\Scripts\python.exe -m ruff format --check .
86 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 36 source files

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

## 10. Final application package layout

Application package after `003-02`:

```text
src/kvc_application/__init__.py
src/kvc_application/dto.py
src/kvc_application/errors.py
src/kvc_application/ports.py
src/kvc_application/services/__init__.py
src/kvc_application/services/identity.py
```

No `kaiten_connection.py`, `crypto.py`, MAX client, UnitOfWork, or service framework was added.

## 11. IdentityService constructor/public API

Implemented:

```python
class IdentityService:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None: ...

    async def resolve_or_onboard_private_max_user(
        self,
        input: ResolveMaxIdentityInput,
    ) -> IdentityResolution: ...
```

The service does not construct an engine, settings, provider client, or repository singleton.

## 12. Transaction ownership implementation

Every attempt opens its own session and transaction:

```python
async with self._sessionmaker() as session:
    async with session.begin():
        ...
```

Repositories receive the same `AsyncSession`. No application commit/rollback call was added.

## 13. Repository composition

Each transaction creates session-bound repositories:

```text
UserRepository
MaxChatRepository
NotificationSettingsRepository
KaitenConnectionRepository
```

`KaitenConnectionRepository` is read-only in this stage and is used only to project `IdentityResolution.kaiten_connection_status`.

## 14. Existing identity resolution behavior

Existing `max_chat_id` path:

```text
lookup max_chat_id
require stored max_user_id matches incoming max_user_id
load user
validate user status
read optional Kaiten connection status
return is_new_user=False
```

Mismatch raises:

```text
IdentityConflict
```

The existing-user path does not repair or recreate notification settings.

## 15. Disabled-user resolution behavior

Disabled users are resolvable:

```text
IdentityResolution.user_status = DISABLED
```

`IdentityService` does not raise `UserDisabled`, re-enable users, or block identity-only MAX chat rotation for disabled users.

## 16. Kaiten connection-status read behavior

Implemented read-only projection:

```text
connection missing -> None
connection exists -> ACTIVE / DISABLED / NEEDS_REAUTH
```

The service does not decrypt, inspect ciphertext, verify Kaiten, or mutate `kaiten_connections`.

## 17. New-user onboarding flow

Unknown private identity flow:

```text
create ACTIVE users row
create primary PRIVATE max_chats row
create notification_settings through get_or_create_for_user
return IdentityResolution(is_new_user=True)
commit on transaction exit
```

All three rows are created atomically in one transaction.

## 18. Notification settings eager creation

The service uses:

```text
NotificationSettingsRepository.get_or_create_for_user(user.id)
```

Integration tests assert:

```text
enabled = false
due_soon_days = 1
timezone = UTC
```

Notifications are not enabled automatically.

## 19. MAX chat rotation algorithm

When `max_chat_id` is not found but the `max_user_id` private binding exists:

```text
lock existing PRIVATE binding by max_user_id
validate PRIVATE and same max_user_id
re-check incoming max_chat_id
raise IdentityConflict if occupied by another row
update only max_chat_id when free
preserve binding id, user id, max_user_id, chat_type, is_primary
return is_new_user=False
```

No delete/insert, second binding, group-chat support, or identity merge was added.

## 20. New MaxChatRepository methods

Added:

```text
get_private_by_max_user_id_for_update(max_user_id)
update_max_chat_id(binding, max_chat_id)
```

Semantics:

```text
PRIVATE-scoped lock lookup
SELECT ... FOR UPDATE
update only max_chat_id
flush/refresh following repository convention
no commit
no rollback
```

No generic update/upsert framework was added.

## 21. Rotation locking proof

Structural repository tests verify:

```text
get_private_by_max_user_id_for_update contains max_user_id filter
get_private_by_max_user_id_for_update contains chat_type == "PRIVATE"
get_private_by_max_user_id_for_update uses .with_for_update()
update_max_chat_id assigns only binding.max_chat_id
update_max_chat_id does not assign user_id, max_user_id, chat_type, or is_primary
```

Integration tests verify rotation updates the existing row and preserves identity fields.

## 22. Identity conflict behavior

Covered conflict cases:

```text
stored U1/C1, incoming U2/C1 -> IdentityConflict
stored U1/C1 and U2/C2, incoming U1/C2 -> IdentityConflict
```

Tests assert no row is stolen or merged.

## 23. Persistence invariant/error mapping

Implemented mapping:

```text
missing user for persisted MAX binding -> PersistenceConflict
unsupported persisted user status -> PersistenceConflict
unsupported persisted Kaiten connection status -> PersistenceConflict
PersistenceInvariantError during identity orchestration -> PersistenceConflict
```

Errors use concise safe messages and do not include raw SQL, constraint dumps, database URLs, passwords, or other users' identifiers.

## 24. Onboarding IntegrityError retry implementation

The public method catches only:

```text
sqlalchemy.exc.IntegrityError
```

Retry behavior:

```text
first attempt allow_onboarding=True
on IntegrityError, transaction context rolls back
retry opens a fresh session/transaction
retry uses allow_onboarding=False
retry resolves persisted winner or surfaces IdentityConflict/PersistenceConflict
second IntegrityError maps to PersistenceConflict
```

No infinite retry loop or arbitrary retry count was added.

## 25. Exactly-one-retry proof

Unit tests prove:

```text
first IntegrityError triggers exactly one retry
retry receives allow_onboarding=False
race-loser result is_new_user=False
second IntegrityError maps to PersistenceConflict
IdentityConflict is not retried or swallowed
```

## 26. is_new_user race semantics

Implemented:

```text
normal first creation -> is_new_user=True
normal repeated lookup -> is_new_user=False
safe rotation -> is_new_user=False
race-loser retry after IntegrityError -> is_new_user=False
```

## 27. Unit tests

Added:

```text
tests/unit/test_identity_service.py
```

Coverage:

```text
IntegrityError exactly-one retry
retry maps second IntegrityError to PersistenceConflict
IdentityConflict is not swallowed
missing bound user maps to PersistenceConflict
```

## 28. Repository tests

Extended:

```text
tests/unit/test_repository_contracts.py
tests/integration/test_repositories_postgresql.py
```

Coverage:

```text
FOR UPDATE lock method shape
PRIVATE filter
update-only max_chat_id source contract
live get_private_by_max_user_id_for_update
live update_max_chat_id preserving non-chat fields
repositories still contain no commit/rollback
```

## 29. PostgreSQL integration tests

Added:

```text
tests/integration/test_identity_service_postgresql.py
```

Coverage:

```text
new onboarding creates ACTIVE user, PRIVATE primary binding, settings defaults
repeat resolution is idempotent
existing Kaiten connection status is projected read-only
disabled user resolves as DISABLED
safe rotation preserves binding/user identity
disabled user rotation remains identity-only and does not re-enable
chat/user mismatch raises IdentityConflict
occupied rotation chat raises IdentityConflict
onboarding rollback prevents partial rows
database returns to clean baseline
```

## 30. Transaction atomicity proof

Integration test injects a synthetic failure in notification-settings creation after user/binding work starts. The service transaction rolls back and the test confirms no MAX binding remains for that synthetic identity.

No production failure hook was added.

## 31. Concurrency/retry proof

Deterministic unit seam proves the retry path without sleeps:

```text
attempt 1 raises IntegrityError
attempt 2 uses a fresh logical resolution path with onboarding disabled
exactly one retry occurs
```

PostgreSQL tests prove uniqueness and locking foundations remain active through the repository integration suite. No flaky sleep-based multi-session race test was added.

## 32. Idempotency proof

Integration tests prove:

```text
same max_user_id + same max_chat_id -> same user and binding
repeated onboarding does not duplicate binding/settings
safe rotation keeps the same binding id
repeat after rotation resolves without another mutation
```

## 33. Database cleanup/baseline restoration

During the first targeted run, cleanup attempted to delete `users` before deleting a test `kaiten_connections` row, leaving one synthetic identity. The cleanup order was corrected, and a targeted cleanup removed only rows whose MAX user id matched:

```text
synthetic-identity-%
```

Cleanup command result:

```text
cleaned synthetic identity users: 1
```

Final database state:

```text
alembic_version=00201_mvp_service_model
dialog_sessions=0
kaiten_connections=0
max_chats=0
notification_history=0
notification_settings=0
pending_commands=0
users=0
```

No broad cleanup of user-created data was performed.

## 34. No provider/crypto/service scope leakage

Confirmed:

```text
no MAX API/client calls
no Kaiten API/client calls
no GigaChat calls
no SaluteSpeech/STT calls
no HTTP client usage
no TokenCipher invocation
no cryptography/Fernet/MultiFernet/AES-GCM
no KaitenConnectionService
no dialog_sessions or pending_commands orchestration
```

## 35. No schema/dependency changes

Confirmed:

```text
pyproject.toml unchanged
Alembic revisions unchanged
models.py unchanged
no new table/column/index/FK/status
no dependency added
no configuration changed
```

## 36. Alembic current/check

Final Alembic diagnostics:

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

## 37. Secret/privacy audit

Checked new/changed application source, repository source, tests, current prompt, and report inputs for secret markers.

Findings:

```text
No real MAX IDs.
No real Kaiten token.
No Authorization header value.
No Bearer token value.
No database password.
No crypto key.
No private card/workspace data.
```

Matches were limited to:

```text
synthetic ciphertext test bytes
field names such as encrypted_api_token
safe application error messages
normative forbidden-word references in the prompt
```

## 38. Full quality gate

Targeted tests:

```text
.venv\Scripts\python.exe -m pytest tests/unit/test_identity_service.py tests/unit/test_repository_contracts.py tests/integration/test_identity_service_postgresql.py tests/integration/test_repositories_postgresql.py -v
36 passed in 5.00s
```

Full gate:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
110 passed in 6.06s

.venv\Scripts\python.exe -m pytest -W error
110 passed in 5.79s

.venv\Scripts\python.exe -m ruff format --check .
90 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 38 source files

git diff --check
<no output, exit code 0>
```

## 39. Changed-file classification

Application production code:

```text
src/kvc_application/__init__.py
src/kvc_application/services/__init__.py
src/kvc_application/services/identity.py
```

Persistence repositories:

```text
src/kvc_persistence/repositories/max_chats.py
```

Tests:

```text
tests/unit/test_identity_service.py
tests/unit/test_imports.py
tests/unit/test_repository_contracts.py
tests/integration/test_identity_service_postgresql.py
tests/integration/test_repositories_postgresql.py
```

Alembic/schema:

```text
none
```

Dependencies:

```text
none
```

Configuration:

```text
none
```

Integrations:

```text
none
```

Prompts:

```text
codex/reports/003_02_identity_onboarding_service_implementation_prompt.md
```

Reports:

```text
codex/reports/003_02_identity_onboarding_service_implementation_report.md
```

Database final state:

```text
alembic_version=00201_mvp_service_model
all seven business tables contain 0 rows
```

Other:

```text
none
```

## 40. Explicit deferred work

Deferred to `003-03`:

```text
TokenCipher concrete cryptography adapter
authenticated encryption implementation
versioned key ring
key configuration/loading
encryption/decryption acceptance
```

Deferred to `003-04`:

```text
KaitenConnectionService
Kaiten credential verifier adapter
bind/replace
disable
get_active_connection_secret
credential snapshot compare-and-mark
mark_needs_reauth
stale credential race handling
```

Still deferred:

```text
MAX transport/bot
GigaChat
STT
dialog orchestration
pending commands
notification worker
```

## 41. Final Git status/diff

Before this report was created:

```text
 M src/kvc_application/__init__.py
 M src/kvc_persistence/repositories/max_chats.py
 M tests/integration/test_repositories_postgresql.py
 M tests/unit/test_imports.py
 M tests/unit/test_repository_contracts.py
?? codex/reports/003_02_identity_onboarding_service_implementation_prompt.md
?? src/kvc_application/services/
?? tests/integration/test_identity_service_postgresql.py
?? tests/unit/test_identity_service.py
```

Tracked diff stat before this report:

```text
src/kvc_application/__init__.py                   |  2 ++
src/kvc_persistence/repositories/max_chats.py     | 17 +++++++++++++++++
tests/integration/test_repositories_postgresql.py | 14 ++++++++++++++
tests/unit/test_imports.py                        |  1 +
tests/unit/test_repository_contracts.py           | 21 +++++++++++++++++++++
5 files changed, 55 insertions(+)
```

Untracked files are not included in plain `git diff --stat` until staged.

Post-report verification:

```text
.venv\Scripts\python.exe -m ruff format --check .
91 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

git diff --check
<no output, exit code 0>

git status --short
 M src/kvc_application/__init__.py
 M src/kvc_persistence/repositories/max_chats.py
 M tests/integration/test_repositories_postgresql.py
 M tests/unit/test_imports.py
 M tests/unit/test_repository_contracts.py
?? codex/reports/003_02_identity_onboarding_service_implementation_prompt.md
?? codex/reports/003_02_identity_onboarding_service_implementation_report.md
?? src/kvc_application/services/
?? tests/integration/test_identity_service_postgresql.py
?? tests/unit/test_identity_service.py

git diff --stat
src/kvc_application/__init__.py                   |  2 ++
src/kvc_persistence/repositories/max_chats.py     | 17 +++++++++++++++++
tests/integration/test_repositories_postgresql.py | 14 ++++++++++++++
tests/unit/test_imports.py                        |  1 +
tests/unit/test_repository_contracts.py           | 21 +++++++++++++++++++++
5 files changed, 55 insertions(+)

git diff --name-status
M src/kvc_application/__init__.py
M src/kvc_persistence/repositories/max_chats.py
M tests/integration/test_repositories_postgresql.py
M tests/unit/test_imports.py
M tests/unit/test_repository_contracts.py
```

## 42. Final status

```text
IMPLEMENTED - READY FOR 003-03 TOKEN CIPHER ADAPTER
```
