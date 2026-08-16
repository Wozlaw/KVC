# 003-02 — IdentityService, MAX onboarding and safe chat rotation implementation

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Функциональная ветка:

```text
003 — Application service layer and user onboarding
```

Текущая рабочая ветка должна быть:

```text
003-application-service-user-onboarding
```

Принятые этапы:

```text
003-00   Application service/user onboarding audit
003-00a  Final application service/user onboarding specification
003-01   Application DTO/port/error contracts implementation
```

Основные нормативные документы:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/002_03_repository_query_contracts_implementation_report.md
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

Финальный статус `003-01`:

```text
IMPLEMENTED - READY FOR 003-02 IDENTITY ONBOARDING SERVICE
```

На этом этапе необходимо:

1. сначала создать **Git checkpoint уже принятого `003-01`**;
2. затем реализовать только:
   - `IdentityService`;
   - first-message onboarding;
   - MAX identity conflict detection;
   - safe `max_chat_id` rotation;
   - eager `notification_settings`;
   - controlled onboarding concurrency retry;
   - минимально необходимые `MaxChatRepository` lock/update primitives;
   - unit + PostgreSQL integration tests;
3. создать report `003-02`.

Не реализовывать Kaiten credential lifecycle, cryptography adapter, MAX transport или command processing.

---

# 1. Главная цель

После `003-02` следующий application use case должен быть полностью реализован:

```text
incoming PRIVATE MAX identity
        ↓
ResolveMaxIdentityInput
        ↓
IdentityService.resolve_or_onboard_private_max_user()
        ↓
existing identity resolution
OR
safe max_chat_id rotation
OR
new KVC user onboarding
        ↓
IdentityResolution
```

Frozen successful first-message invariant:

```text
users
+
max_chats
+
notification_settings
```

создаются атомарно в одной caller-owned DB transaction.

Frozen repeated-message invariant:

```text
same max_user_id + same max_chat_id
    -> same KVC user
    -> same MAX binding
    -> no duplicate notification_settings
```

Frozen rotation invariant:

```text
same max_user_id + new unbound max_chat_id
    -> update the same existing PRIVATE binding
    -> do not create another KVC user
```

Frozen conflict invariant:

```text
incoming max_chat_id belongs to another MAX identity/KVC user
    -> IdentityConflict
```

---

# 2. Источники истины и приоритет

Перед implementation обязательно изучи:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/002_03_repository_query_contracts_implementation_report.md
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

Также изучи фактический код:

```text
src/kvc_application/
src/kvc_persistence/models.py
src/kvc_persistence/repositories/
src/kvc_persistence/session.py
src/kvc_persistence/engine.py
tests/unit/
tests/integration/
pyproject.toml
```

Приоритет:

```text
003-00a final specification
    >
003-01 accepted implementation contract
    >
002-04 accepted persistence closeout
    >
002-03 repository implementation
```

Не переоткрывать решения `003-00a`.

Если фактический source противоречит frozen contract и это невозможно исправить узко без архитектурного решения:

```text
BLOCKED - FROZEN CONTRACT CONFLICT
```

---

# 3. Frozen repository baseline

Из `002-03` уже существуют:

## UserRepository

```text
get_by_id(user_id)
get_by_id_for_update(user_id)
create(user_id=None, status=None)
set_status(user, status)
```

## MaxChatRepository

```text
get_by_max_chat_id(max_chat_id)
get_private_by_max_user_id(max_user_id)
get_primary_for_user(user_id)
create_private_binding(user_id, max_user_id, max_chat_id, ...)
```

## KaitenConnectionRepository

```text
get_for_user(user_id)
get_for_user_for_update(user_id)
create(...)
update_connection(...)
```

## NotificationSettingsRepository

```text
get_for_user(user_id)
get_for_user_for_update(user_id)
get_or_create_for_user(user_id)
list_enabled()
```

Repository layer:

```text
receives AsyncSession
does not commit
does not rollback
may execute / flush / refresh
```

Application layer owns transaction boundaries.

Do not reimplement these capabilities inside `IdentityService`.

---

# 4. Required repository extension — exact scope

`003-00a` froze exactly the missing primitives required for safe MAX rotation.

Add to `MaxChatRepository`:

```python
async def get_private_by_max_user_id_for_update(
    self,
    max_user_id: str,
) -> MaxChat | None: ...
```

and:

```python
async def update_max_chat_id(
    self,
    binding: MaxChat,
    max_chat_id: str,
) -> MaxChat: ...
```

Exact semantics:

### `get_private_by_max_user_id_for_update`

```text
same filtering semantics as get_private_by_max_user_id
PRIVATE only
SELECT ... FOR UPDATE
returns ORM MaxChat | None
does not commit
does not rollback
```

### `update_max_chat_id`

```text
updates only binding.max_chat_id
flushes if required by current repository convention
returns the same/refreshed MaxChat object
does not create another binding
does not change user_id
does not change max_user_id
does not change chat_type
does not change primary semantics
does not commit
does not rollback
```

Do not add generic update methods.

Do not add:

```text
rebind service
merge identities
delete old binding
group-chat support
upsert framework
repository transaction ownership
```

No schema change is required.

---

# 5. Git checkpoint — mandatory before `003-02` source changes

`003-01` was accepted by the user, but its implementation/report artifacts are still uncommitted.

Before modifying `IdentityService` or repositories, create a checkpoint commit for the accepted work.

## 5.1. Inspect current state

Run:

```powershell
git branch --show-current
git status --short
git status --ignored --short
git log --oneline --decorate --graph -10
git diff --check
git diff --stat
git diff --name-status
```

Expected branch:

```text
003-application-service-user-onboarding
```

Expected accepted `003-01` changes include approximately:

```text
src/kvc_application/__init__.py
src/kvc_application/dto.py
src/kvc_application/errors.py
src/kvc_application/ports.py

tests/unit/test_application_dto_contracts.py
tests/unit/test_application_error_contracts.py
tests/unit/test_application_port_contracts.py

codex/prompts/003_00_*.md
codex/prompts/003_00a_*.md
codex/prompts/003_01_*.md

codex/reports/003_00_*.md
codex/reports/003_00a_*.md
codex/reports/003_01_*.md
```

The current `003-02` prompt itself may already exist as an untracked input:

```text
codex/prompts/003_02_identity_onboarding_service_implementation_prompt.md
```

It is **not** part of the accepted `003-01` checkpoint and must not force a false "dirty worktree" blocker.

---

# 6. Pre-checkpoint acceptance gate

Before staging the accepted `003-01` artifacts, rerun:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip check

.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error

.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src

.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check

git diff --check
```

Expected accepted baseline:

```text
Python 3.12.9
pip check PASS
pytest = 94 passed
pytest -W error = 94 passed
ruff PASS
mypy PASS
Alembic current = 00201_mvp_service_model
Alembic check = no new upgrade operations detected
```

If the test count changes only because the current prompt/report is present, that is not itself a blocker.

If source/tests fail, do not checkpoint until the accepted `003-01` state is understood.

---

# 7. Checkpoint diff and secret audit

Before staging:

1. inspect all accepted `003-01` source/tests/docs;
2. confirm no unrelated files are mixed in;
3. confirm no real secrets.

Search new/changed accepted files for markers such as:

```text
Authorization
Bearer
Kaiten token
api_token
password
encryption key
PRIVATE KEY
```

Distinguish normative text and synthetic fake values from real secrets.

Never print a discovered real secret.

If a real secret is present:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

---

# 8. Stage accepted `003-01` artifacts explicitly

Do **not** use:

```text
git add .
```

Stage only accepted artifacts from:

```text
003-00
003-00a
003-01
```

plus their application source/tests.

Example explicit categories:

```text
src/kvc_application/
tests/unit/test_application_*_contracts.py
codex/prompts/003_00_*.md
codex/prompts/003_00a_*.md
codex/prompts/003_01_*.md
codex/reports/003_00_*.md
codex/reports/003_00a_*.md
codex/reports/003_01_*.md
```

Do not stage current:

```text
codex/prompts/003_02_identity_onboarding_service_implementation_prompt.md
```

unless it was already intentionally tracked by project workflow.

After staging:

```powershell
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
git status --short
```

Review the staged diff.

---

# 9. Create `003-01` checkpoint commit

If and only if the staged content is exactly the accepted `003-00/00a/01` work and all gates pass, create:

```powershell
git commit -m "feat: add application service contracts"
```

Do not amend existing commits.

Do not squash branch `002`.

Do not push.

Do not merge.

After commit:

```powershell
git log --oneline --decorate -5
git status --short
git diff --check
```

Expected worktree after checkpoint:

```text
clean
```

except possibly the current untracked:

```text
codex/prompts/003_02_identity_onboarding_service_implementation_prompt.md
```

Record checkpoint SHA in the `003-02` report.

If unrelated dirty files remain, do not delete them; classify them and continue only if they are clearly unrelated and safe.

---

# 10. `003-02` implementation package shape

Preferred application structure:

```text
src/kvc_application/
    __init__.py
    dto.py
    errors.py
    ports.py
    services/
        __init__.py
        identity.py
```

Create:

```text
src/kvc_application/services/__init__.py
src/kvc_application/services/identity.py
```

if no service package exists yet.

Do not create:

```text
kaiten_connection.py
crypto.py
max_client.py
unit_of_work.py
```

on this stage.

Expose `IdentityService` through an appropriate application import surface if current project conventions support it.

---

# 11. `IdentityService` constructor — frozen contract

Implement:

```python
class IdentityService:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._sessionmaker = sessionmaker
```

or an equivalent strictly typed constructor.

Do not inject repositories as global/singleton objects because repositories are session-bound.

Do not construct:

```text
engine
sessionmaker
provider clients
settings
```

inside the service.

Do not load `.env`.

---

# 12. Public service API — exact contract

Implement:

```python
async def resolve_or_onboard_private_max_user(
    self,
    input: ResolveMaxIdentityInput,
) -> IdentityResolution: ...
```

Use the already accepted DTOs and errors from `003-01`.

Do not define duplicate local DTOs.

Do not return ORM entities.

Do not return SQLAlchemy session objects.

---

# 13. Transaction ownership

Each resolution attempt owns its session/transaction:

```python
async with self._sessionmaker() as session:
    async with session.begin():
        ...
```

Repositories receive the same `AsyncSession`.

Repository methods still do not:

```text
commit
rollback
```

A successful call commits by exiting `session.begin()`.

An exception rolls back the transaction.

Do not add UnitOfWork.

Do not add nested application commits.

---

# 14. Repository composition inside an attempt

Inside each transaction create/use session-bound:

```text
UserRepository
MaxChatRepository
NotificationSettingsRepository
KaitenConnectionRepository
```

`KaitenConnectionRepository` is used here **read-only** only to populate:

```text
IdentityResolution.kaiten_connection_status
```

Do not implement any Kaiten connection lifecycle operation.

---

# 15. Identity resolution — top-level ordering

Frozen algorithm:

```text
1. Lookup by incoming max_chat_id.
2. If found:
       require stored max_user_id == incoming max_user_id.
       resolve existing user.
       return current connection status.
3. If max_chat_id is not found:
       lookup PRIVATE binding by max_user_id.
4. If binding by max_user_id exists:
       perform safe max_chat_id rotation.
       resolve existing user.
       return current connection status.
5. If neither binding exists:
       create new ACTIVE KVC user.
       create primary PRIVATE MAX binding.
       eagerly create notification_settings defaults.
       return new identity.
```

No identity merge.

No transport behavior.

No external call.

---

# 16. Existing binding by `max_chat_id`

When:

```text
binding = MaxChatRepository.get_by_max_chat_id(input.max_chat_id)
```

returns a row:

## Match

If:

```text
binding.max_user_id == input.max_user_id
```

then:

```text
resolve user by binding.user_id
read Kaiten connection status if any
return IdentityResolution(
    user_id=...,
    max_chat_binding_id=binding.id,
    user_status=...,
    is_new_user=False,
    kaiten_connection_status=...,
)
```

Do not create notification settings in this existing-user path as a hidden repair unless frozen contract explicitly requires it.

`003-00a` requires eager creation during onboarding; ordinary identity resolution remains a pure resolution path.

If historical data unexpectedly lacks settings, do not silently turn every lookup into a repair framework. Surface/report only if tests reveal a real accepted-baseline inconsistency.

## Mismatch

If:

```text
binding.max_user_id != input.max_user_id
```

raise:

```text
IdentityConflict
```

Do not inspect or reveal another user's details in the exception.

---

# 17. Existing user lookup invariant

Any MAX binding must point to an existing KVC user due FK/invariant.

If a binding is found but:

```text
UserRepository.get_by_id(binding.user_id) is None
```

this is persistence corruption/invariant failure.

Map it to:

```text
PersistenceConflict
```

or the accepted application persistence failure form.

Do not create a replacement user automatically.

Do not expose raw SQLAlchemy/persistence internals in user-facing error text.

---

# 18. Disabled-user identity semantics

Identity resolution is allowed for:

```text
ACTIVE
DISABLED
```

For a disabled existing user:

```text
IdentityResolution.user_status = "DISABLED"
```

Do not raise `UserDisabled` from identity resolution itself.

Do not re-enable the user.

Safe identity-only chat rotation remains allowed for disabled users as frozen by `003-00a`.

All business command rejection for disabled users belongs to later user-facing workflows.

---

# 19. Reading Kaiten connection status

For an existing or newly created user, use:

```text
KaitenConnectionRepository.get_for_user(user_id)
```

read-only.

Map:

```text
connection is None
    -> kaiten_connection_status = None

connection exists
    -> kaiten_connection_status = connection.status
```

Do not decrypt token.

Do not inspect ciphertext.

Do not update connection.

Do not validate Kaiten.

For a newly onboarded user this is expected to be `None`, but use a coherent result-building helper if that keeps the service simple.

---

# 20. New-user onboarding path

If neither:

```text
max_chat_id binding
nor
PRIVATE max_user_id binding
```

exists, create:

```text
User(status="ACTIVE")
PRIVATE primary MaxChat binding
NotificationSettings defaults
```

all in **one transaction**.

Preferred sequence:

```text
1. UserRepository.create(status="ACTIVE")
2. MaxChatRepository.create_private_binding(...)
3. NotificationSettingsRepository.get_or_create_for_user(user.id)
4. optionally read Kaiten connection status
5. return IdentityResolution(is_new_user=True)
6. commit on transaction exit
```

Use actual repository signatures.

Do not invent parameters that are not present.

If `create_private_binding` already defaults:

```text
chat_type=PRIVATE
is_primary=True
```

follow its accepted API; pass explicit values only if the real signature requires or benefits from clarity.

---

# 21. Notification settings contract

During first onboarding:

```text
notification_settings row must exist before commit
```

Frozen values:

```text
enabled = false
due_soon_days = 1
timezone = "UTC"
```

Prefer existing:

```text
NotificationSettingsRepository.get_or_create_for_user(user_id)
```

because it already implements accepted defaults and caller-owned transaction semantics.

Do not duplicate default construction logic in `IdentityService` if repository/model defaults already own the physical defaults.

After creation, tests must assert the frozen values.

Do not enable notifications automatically.

---

# 22. Safe MAX chat rotation — required algorithm

When:

```text
incoming max_chat_id not found
existing PRIVATE binding found by max_user_id
```

execute safe rotation.

Required algorithm:

```text
1. Re-read/lock existing PRIVATE binding using:
       get_private_by_max_user_id_for_update(max_user_id)
2. If locked binding disappeared:
       treat as concurrency/persistence conflict and resolve safely;
       do not blindly create another identity inside the stale path.
3. Confirm:
       binding.max_user_id == incoming max_user_id
       binding.chat_type == "PRIVATE"
4. Re-check incoming max_chat_id using:
       get_by_max_chat_id(incoming max_chat_id)
5. If incoming max_chat_id is bound to another row/user:
       raise IdentityConflict
6. If incoming max_chat_id is already the same locked binding:
       treat as idempotent success.
7. Otherwise:
       update_max_chat_id(binding, incoming max_chat_id)
8. Preserve:
       same binding.id
       same binding.user_id
       same binding.max_user_id
       PRIVATE
       primary semantics
9. Resolve user and current Kaiten status.
10. Return:
       is_new_user=False
```

No delete+insert rotation.

No second binding.

No user merge.

---

# 23. Rotation conflict privacy

`IdentityConflict` messages must be safe.

Allowed diagnostic information:

```text
operation name
generic binding conflict
incoming external ID only if project error policy already treats it as non-secret
```

Prefer not to include:

```text
other user UUID
other max_user_id
other binding details
database constraint dumps
```

No real MAX identity appears in tests/reports; use synthetic values.

---

# 24. Rotation idempotency

Required cases:

### Same existing pair

```text
stored max_user_id = U1
stored max_chat_id = C1
incoming = U1/C1
    -> existing resolution
    -> no update
```

### Safe rotation

```text
stored = U1/C1
incoming = U1/C2
C2 unbound
    -> same binding id
    -> max_chat_id becomes C2
    -> is_new_user=False
```

### Repeat rotated pair

```text
stored after rotation = U1/C2
incoming = U1/C2
    -> existing resolution
    -> no further mutation
```

---

# 25. Conflict matrix — mandatory

Implement/test at least:

| Stored state | Incoming | Result |
|---|---|---|
| none | U1/C1 | create user + binding + settings |
| U1/C1 | U1/C1 | resolve existing |
| U1/C1 | U1/C2, C2 free | safe rotation |
| U1/C1 and U2/C2 | U1/C2 | `IdentityConflict` |
| U1/C1 | U2/C1 | `IdentityConflict` |
| disabled U1/C1 | U1/C1 | resolve DISABLED |
| disabled U1/C1 | U1/C2 free | safe identity rotation, still DISABLED |

Use synthetic IDs only.

---

# 26. First-message concurrency contract

Frozen behavior:

```text
two concurrent messages for the same unknown MAX identity
```

may both initially observe no binding.

Database UNIQUE constraints remain final race guards.

Required service behavior:

```text
attempt 1:
    run normal resolution/onboarding transaction

if a known IntegrityError occurs during create/flush/commit:
    transaction rolls back

retry:
    open a fresh session/transaction
    resolve identity once more from persisted state

if retry resolves coherent same identity:
    return IdentityResolution(is_new_user=False or coherent accepted result)

if retry finds an identity conflict:
    raise IdentityConflict

if retry cannot establish coherent state:
    raise PersistenceConflict
```

No infinite retry.

No loop with arbitrary retry count.

Exactly one controlled retry for onboarding uniqueness race.

---

# 27. IntegrityError handling boundary

Do not catch every exception as retryable.

Catch only:

```text
sqlalchemy.exc.IntegrityError
```

around the first transaction attempt where a uniqueness race can occur.

Do not swallow:

```text
IdentityConflict
PersistenceConflict
programming errors
type errors
unexpected repository errors
```

The transaction context must perform rollback naturally before retry.

The retry must use a **new session/transaction**, not reuse a failed SQLAlchemy transaction.

---

# 28. Distinguish race from real conflict

After `IntegrityError`, the retry resolution determines semantics.

Examples:

### Same identity won elsewhere

```text
retry sees U1/C1
    -> return same KVC user
```

### Conflicting binding won elsewhere

```text
retry sees C1 bound to U2
    -> IdentityConflict
```

### State still missing/incoherent

```text
retry cannot resolve expected identity
    -> PersistenceConflict
```

Do not inspect PostgreSQL constraint-name strings as the sole business decision mechanism if state re-read can determine the accepted result.

Constraint names may be diagnostic only.

---

# 29. Suggested internal structure — keep small

A clean implementation may use private helpers, for example:

```text
_resolve_once(...)
_resolve_existing_binding(...)
_rotate_existing_binding(...)
_onboard_new_user(...)
_build_resolution(...)
```

This is optional.

Do not over-fragment into a framework.

Do not introduce service base classes.

Do not introduce handler registries.

Do not create repository wrappers.

The public API remains one method.

---

# 30. `is_new_user` semantics under race

Normal first creation:

```text
is_new_user=True
```

Repeated normal lookup:

```text
is_new_user=False
```

Race loser after rollback/retry:

```text
is_new_user=False
```

because that specific request did not commit the user creation.

Document/test this explicitly.

Do not attempt distributed "both requests report true" semantics.

---

# 31. User status on creation

New KVC user must be:

```text
ACTIVE
```

Use the existing repository/model accepted status API.

Do not introduce another onboarding status.

Do not create:

```text
PENDING
UNVERIFIED
NEW
```

---

# 32. MAX chat type

MVP identity contract is:

```text
PRIVATE only
```

Do not add group-chat support.

`ResolveMaxIdentityInput.chat_type` is already:

```text
Literal["PRIVATE"]
```

The service may defensively enforce PRIVATE if current project style has a clear safe contract-misuse exception, but do **not** invent a new product-facing error class for this stage.

Do not broaden the DTO to `str`.

Do not change frozen aliases from `003-01`.

---

# 33. Application error mapping

Use already implemented:

```text
IdentityConflict
PersistenceConflict
```

`UserDisabled` is not raised by identity resolution.

Do not add new application error classes unless a genuine frozen-contract gap blocks implementation.

Raw:

```text
IntegrityError
PersistenceInvariantError
SQLAlchemy exception
```

must not become the normal public outcome of a known onboarding race.

Unexpected programming errors must not be hidden.

---

# 34. PersistenceInvariantError mapping

If a repository raises `PersistenceInvariantError` because the accepted DB/repository contract is unexpectedly broken during identity orchestration:

```text
map to PersistenceConflict
```

only where it represents a persistence-state/invariant failure.

Do not convert all repository exceptions indiscriminately.

Preserve exception chaining:

```python
raise PersistenceConflict(...) from exc
```

without leaking secrets.

---

# 35. No external calls

`IdentityService` must perform **zero** calls to:

```text
MAX API
Kaiten API
GigaChat
SaluteSpeech
HTTP clients
```

Incoming MAX IDs are already normalized transport input.

Do not add a MAX verifier port.

Do not call Kaiten just to get connection status; use KVC persistence only.

---

# 36. No crypto work

Do not implement or invoke:

```text
TokenCipher
cryptography
Fernet
MultiFernet
key ring
token decrypt
token encrypt
```

`KaitenConnectionRepository` is read-only in this stage and only exposes status.

Crypto begins at:

```text
003-03
```

---

# 37. No Kaiten connection service

Do not create:

```text
KaitenConnectionService
bind_or_replace_connection
disable_connection
get_active_connection_secret
mark_needs_reauth
```

These belong to:

```text
003-04
```

Do not move stale-credential work into `003-02`.

---

# 38. No transport integration

Do not create:

```text
MAX polling
MAX webhook
bot handler
FastAPI onboarding endpoint
CLI onboarding command
message parsing
response text
```

Transport integration is future work.

Tests call `IdentityService` directly.

---

# 39. No dialog/pending-command work

Do not create or mutate:

```text
dialog_sessions
pending_commands
```

Identity resolution must not automatically open a dialog session.

Context management is a separate future application workflow.

---

# 40. Schema invariant

Do not change:

```text
users
max_chats
kaiten_connections
notification_settings
```

or any other table.

Forbidden:

```text
new column
new index
new UNIQUE
new FK
new status
new Alembic revision
manual DDL
```

Alembic remains:

```text
00201_mvp_service_model
```

If safe MAX rotation cannot be implemented without schema change contrary to `003-00a`:

```text
BLOCKED - FROZEN CONTRACT CONFLICT
```

Do not create migration.

---

# 41. Dependency invariant

Expected dependency changes:

```text
none
```

Do not add libraries.

Use existing:

```text
SQLAlchemy
asyncpg
pytest
pytest-asyncio
```

and existing test infrastructure.

Do not add retry libraries.

---

# 42. Unit tests — service behavior

Create focused tests, for example:

```text
tests/unit/test_identity_service.py
```

or existing convention equivalent.

Unit tests must cover at least:

```text
existing identity resolves
existing identity returns Kaiten status when present
disabled existing identity resolves as DISABLED
chat-id/max-user mismatch -> IdentityConflict
new identity -> is_new_user=True
new identity creates settings
safe rotation -> same user/binding
repeat after rotation is idempotent
conflicting rotation -> IdentityConflict
missing bound user -> PersistenceConflict
one IntegrityError -> exactly one fresh retry
race-loser retry -> is_new_user=False
second/incoherent failure -> PersistenceConflict
```

Prefer test doubles/fake session/repository seams only if they remain simpler than the real code.

Do not build a mock framework.

---

# 43. Repository unit/structural tests

Extend repository tests to prove:

```text
get_private_by_max_user_id_for_update compiles SELECT ... FOR UPDATE
PRIVATE filter remains present
update_max_chat_id changes only max_chat_id
repository still contains no commit()
repository still contains no rollback()
```

Do not make brittle source-text assertions where SQLAlchemy compiled statement/behavior tests are more robust.

---

# 44. PostgreSQL integration tests — safety prerequisites

Live repository/service behavior must use configured development PostgreSQL only if:

```text
KVC_APP_ENV = development
current_database() = kvc_dev
alembic_version = 00201_mvp_service_model
```

Follow existing integration-test safety convention.

Never mutate an unknown DB.

Use only synthetic:

```text
UUIDs
MAX user IDs
MAX chat IDs
encrypted token bytes if a read-only connection-status fixture is needed
```

No live user identifiers.

No live credentials.

Every test must rollback/cleanup and leave business row counts at baseline.

---

# 45. PostgreSQL integration matrix — IdentityService

Add integration coverage at minimum:

## New onboarding

Prove:

```text
one ACTIVE users row
one PRIVATE primary max_chats row
one notification_settings row
enabled=false
due_soon_days=1
timezone=UTC
IdentityResolution.is_new_user=True
```

inside test transaction semantics.

## Repeat resolution

Call again with same identity and prove:

```text
same user_id
same max_chat_binding_id
is_new_user=False
no duplicate user
no duplicate binding
no duplicate settings
```

## Disabled user

Create/mark disabled user and prove:

```text
identity still resolves
user_status=DISABLED
```

## Safe rotation

Prove:

```text
binding id unchanged
user id unchanged
max_user_id unchanged
max_chat_id changes C1 -> C2
one binding remains
is_new_user=False
```

## Conflict

Prove:

```text
U1/C1
U2/C2
incoming U1/C2
    -> IdentityConflict
no rows stolen/merged
```

---

# 46. Concurrency test strategy

Concurrency is important, but tests must remain deterministic and non-flaky.

Required proof consists of two layers:

## Layer A — service retry-path test

Use deterministic fault injection/unit seam to prove:

```text
first onboarding attempt raises IntegrityError
failed transaction is abandoned
service opens a fresh second attempt
second attempt resolves existing identity
exactly one retry occurs
result is_new_user=False
```

Do not use `sleep()`.

## Layer B — PostgreSQL uniqueness/locking proof

Use real PostgreSQL to prove:

```text
MAX uniqueness remains final guard
FOR UPDATE rotation path works
two users cannot own same private max_user_id/max_chat_id
```

If a deterministic two-session service-level race can be implemented using explicit asyncio synchronization primitives without production hooks or sleeps, add it.

If not, do not introduce flaky timing-based tests merely to claim concurrency coverage. Document that full adversarial multi-session stress belongs to `003-05`.

---

# 47. Optional deterministic concurrent service call

If current test architecture makes it clean, test:

```python
await asyncio.gather(
    service.resolve_or_onboard_private_max_user(input),
    service.resolve_or_onboard_private_max_user(input),
)
```

Expected:

```text
same user_id
same binding_id
one database user
one database binding
one settings row
```

But this test alone does not guarantee the race path actually occurred.

Therefore it supplements, not replaces, deterministic retry-path fault injection.

Do not repeat hundreds of iterations.

---

# 48. Rotation locking test

At minimum prove generated/query path:

```text
get_private_by_max_user_id_for_update
    -> SELECT ... FOR UPDATE
```

For live behavior:

```text
rotation updates locked existing row
```

If deterministic two-session row-lock blocking can be safely asserted without sleeps, add it.

Otherwise reserve deeper blocking timing acceptance for `003-05`.

---

# 49. Transaction atomicity tests

Prove onboarding is atomic.

At minimum test an injected failure after:

```text
user creation
```

or after:

```text
binding creation
```

before transaction completion, then confirm after rollback:

```text
no partial user
no partial binding
no partial settings
```

Use test/session technique consistent with existing project fixtures.

Do not add production failure hooks.

---

# 50. No hidden repair behavior

For an existing coherent identity, the service should not mutate unrelated state.

Do not:

```text
recreate notification settings on every lookup
reset user status
touch Kaiten connection
start dialog
rewrite binding unnecessarily
update timestamps without actual mutation
```

A normal repeated identity resolution should be logically read-only.

---

# 51. Result-building contract

Every successful call returns exactly:

```text
user_id
max_chat_binding_id
user_status
is_new_user
kaiten_connection_status
```

No ORM entity.

No settings object.

No MAX IDs unless already defined in DTO contract.

No secrets.

---

# 52. Export surface

After implementation, allow coherent import, for example:

```python
from kvc_application.services import IdentityService
```

and optionally:

```python
from kvc_application import IdentityService
```

if package root already acts as explicit public surface.

Keep `__all__` exact if used.

Do not export repository classes from `kvc_application`.

---

# 53. Type safety

New source must pass:

```text
mypy src
```

Avoid:

```text
Any
# type: ignore
cast(...)
```

unless objectively required and narrowly justified.

Repository-returned ORM status strings may need typed narrowing to `UserStatus` / `KaitenConnectionStatus`.

Prefer a small explicit mapping/narrowing helper over broad casts if mypy requires proof.

Do not silently coerce unknown statuses.

If persistence contains a status outside the frozen finite set, treat that as:

```text
PersistenceConflict
```

rather than returning an invalid DTO.

---

# 54. Status validation at persistence boundary

Because ORM fields are runtime strings, `IdentityService` should ensure values returned in typed DTOs belong to frozen sets.

For user:

```text
ACTIVE
DISABLED
```

For Kaiten connection:

```text
ACTIVE
DISABLED
NEEDS_REAUTH
```

If the DB somehow contains another value despite CHECK constraints:

```text
PersistenceConflict
```

Do not use unsafe `cast()` as the only runtime guarantee.

Keep this validation small and local.

---

# 55. Error messages

Application error messages should be concise and diagnostic.

Allowed:

```text
MAX identity binding conflict
persisted MAX binding references missing user
unsupported persisted user status
identity onboarding persistence conflict
```

Avoid:

```text
raw SQL
constraint dump
database URL
password
MAX provider payload
other user's identifiers
```

Tests should generally assert error type, not fragile full message text.

---

# 56. Baseline before `003-02` implementation

After the `003-01` checkpoint commit and before source modification, record:

```powershell
git branch --show-current
git log --oneline --decorate -5
git status --short

.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src
.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

The only dirty artifact at this point may be the current `003-02` prompt.

---

# 57. Targeted test gate

After implementation run targeted tests first.

At minimum:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_identity_service.py -v
```

plus repository contract tests containing new MAX lock/update coverage and relevant integration tests.

Example:

```powershell
.venv\Scripts\python.exe -m pytest `
  tests/unit/test_identity_service.py `
  tests/unit/test_repository_contracts.py `
  tests/integration/test_identity_service_postgresql.py `
  -v
```

Adapt paths to actual project structure.

Report:

```text
collected
passed
skipped
warnings
```

No warnings allowed under final `-W error` gate.

---

# 58. Full quality gate

After all implementation/tests:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip check

.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error

.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src

.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check

git diff --check
git status --short
git diff --stat
git diff --name-status
```

Expected:

```text
test count > 94
pytest PASS
pytest -W error PASS
Ruff PASS
mypy PASS
Alembic current = 00201_mvp_service_model
Alembic check = no drift
```

---

# 59. Development database cleanup verification

After PostgreSQL integration tests verify:

```text
alembic_version = 00201_mvp_service_model
```

and no synthetic rows remain from this stage.

Expected business row counts should return to the pre-test baseline, which was previously all zero unless the user has intentionally added development data since then.

Do not delete user-created development data to force a zero count.

If baseline was non-zero at test start:

```text
record baseline counts
run transaction-isolated tests
verify counts return exactly to that baseline
```

Never run broad cleanup against unknown rows.

---

# 60. Secret/privacy audit

Before report, inspect new/changed:

```text
application source
repository source
tests
current prompt
report
```

for real:

```text
MAX IDs
Kaiten token
Authorization header
database password
crypto key
private card/workspace data
```

Only synthetic values in tests.

Do not include actual `.env` values in report.

---

# 61. Diff scope audit

Expected `003-02` production changes after checkpoint:

```text
src/kvc_application/services/__init__.py
src/kvc_application/services/identity.py
possibly src/kvc_application/__init__.py

src/kvc_persistence/repositories/max_chats.py
possibly repository package export file
```

Tests:

```text
unit identity-service tests
repository lock/update tests
PostgreSQL identity-service tests
```

Prompt/report:

```text
codex/prompts/003_02_identity_onboarding_service_implementation_prompt.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
```

Unexpected changes to:

```text
models.py
Alembic
pyproject.toml
kvc_integrations
kvc_api
kvc_worker
```

must be investigated and normally reverted/not introduced.

---

# 62. Git discipline after checkpoint

The initial accepted `003-01` checkpoint commit **is required and authorized by this task**.

After that checkpoint:

```text
do not commit 003-02 implementation automatically
```

Leave `003-02` implementation/report in worktree for review.

Do not:

```text
push
merge
rebase
amend checkpoint
force reset
clean -fd
```

Do not stage all `003-02` files at the end unless needed temporarily for a diff audit; if staging is used only for inspection, return them to the intended review state without discarding content.

---

# 63. Implementation report

Create:

```text
codex/reports/003_02_identity_onboarding_service_implementation_report.md
```

Report must include at minimum:

1. Executive summary.
2. Frozen sources and precedence.
3. Initial Git/worktree state.
4. Pre-checkpoint quality gate.
5. Accepted `003-01` staged inventory.
6. Checkpoint secret audit.
7. Checkpoint commit SHA/message.
8. Post-checkpoint branch/worktree state.
9. `003-02` baseline gate.
10. Final application package layout.
11. `IdentityService` constructor/public API.
12. Transaction ownership implementation.
13. Repository composition.
14. Existing identity resolution behavior.
15. Disabled-user resolution behavior.
16. Kaiten connection-status read behavior.
17. New-user onboarding flow.
18. Notification settings eager creation.
19. MAX chat rotation algorithm.
20. New `MaxChatRepository` methods.
21. Rotation locking proof.
22. Identity conflict behavior.
23. Persistence invariant/error mapping.
24. Onboarding `IntegrityError` retry implementation.
25. Exactly-one-retry proof.
26. `is_new_user` race semantics.
27. Unit tests.
28. Repository tests.
29. PostgreSQL integration tests.
30. Transaction atomicity proof.
31. Concurrency/retry proof.
32. Idempotency proof.
33. Database cleanup/baseline restoration.
34. No provider/crypto/service scope leakage.
35. No schema/dependency changes.
36. Alembic current/check.
37. Secret/privacy audit.
38. Full quality gate.
39. Changed-file classification.
40. Explicit deferred work.
41. Final Git status/diff.
42. Final status.

---

# 64. Changed-file classification in report

Use:

```text
Application production code:
Persistence repositories:
Tests:
Alembic/schema:
Dependencies:
Configuration:
Integrations:
Prompts:
Reports:
Database final state:
Other:
```

Expected:

```text
Alembic/schema:
none

Dependencies:
none

Configuration:
none

Integrations:
none
```

---

# 65. Explicit deferred work

Report must clearly leave for `003-03`:

```text
TokenCipher concrete cryptography adapter
authenticated encryption implementation
versioned key ring
key configuration/loading
encryption/decryption acceptance
```

and for `003-04`:

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

Also still deferred:

```text
MAX transport/bot
GigaChat
STT
dialog orchestration
pending commands
notification worker
```

These are not incomplete `003-02` work.

---

# 66. Acceptance criteria

`003-02` is complete only if:

## Git checkpoint

- branch is `003-application-service-user-onboarding`;
- accepted `003-01` state passed the gate;
- accepted `003-00/00a/01` artifacts were explicitly reviewed;
- no secret was committed;
- checkpoint commit exists;
- checkpoint commit message is coherent;
- current `003-02` prompt was not accidentally mixed into accepted `003-01` checkpoint unless intentionally already tracked.

## Repository extension

- `get_private_by_max_user_id_for_update()` exists;
- it is PRIVATE-scoped;
- it uses `FOR UPDATE`;
- `update_max_chat_id()` changes only `max_chat_id`;
- repositories still do not commit/rollback;
- no generic repository framework added.

## IdentityService

- `IdentityService` exists;
- constructor receives `async_sessionmaker[AsyncSession]`;
- public API exactly accepts `ResolveMaxIdentityInput`;
- returns `IdentityResolution`;
- same chat/user resolves same identity;
- conflicting chat/user raises `IdentityConflict`;
- missing persisted parent maps to `PersistenceConflict`;
- disabled user resolves without reactivation;
- Kaiten connection status is read-only and correctly projected.

## Onboarding

- unknown PRIVATE identity auto-creates ACTIVE KVC user;
- primary PRIVATE MAX binding is created;
- notification settings are created in the same transaction;
- defaults are `false / 1 / UTC`;
- successful new request returns `is_new_user=True`;
- repeated request returns `is_new_user=False`;
- no duplicate rows appear.

## Rotation

- same `max_user_id` + new free `max_chat_id` rotates the existing row;
- binding ID remains unchanged;
- user ID remains unchanged;
- max_user_id remains unchanged;
- PRIVATE/primary semantics remain unchanged;
- occupied incoming chat raises `IdentityConflict`;
- no identity merge;
- repeated rotated request is idempotent.

## Concurrency

- onboarding uniqueness failure is caught only as known `IntegrityError`;
- failed attempt uses rollback via transaction context;
- retry uses fresh session/transaction;
- exactly one retry;
- race loser can resolve winning identity;
- race-loser result is `is_new_user=False`;
- unresolved/incoherent retry becomes `PersistenceConflict`;
- no infinite retry.

## Atomicity

- onboarding cannot leave partial user/binding/settings rows after failure;
- integration test cleanup returns DB to initial baseline.

## Boundaries

- no external API calls;
- no MAX transport;
- no Kaiten credential lifecycle;
- no cryptography implementation;
- no dialog/pending command logic;
- no schema change;
- no migration;
- no dependency change;
- no real secrets/test identities.

## Gate

- targeted tests PASS;
- full pytest PASS;
- `pytest -W error` PASS;
- Ruff PASS;
- mypy PASS;
- `alembic current = 00201_mvp_service_model`;
- `alembic check` reports no new upgrade operations;
- `git diff --check` PASS;
- report created.

---

# 67. Final status

If all acceptance criteria pass:

```text
IMPLEMENTED - READY FOR 003-03 TOKEN CIPHER ADAPTER
```

If the accepted repository/schema cannot support safe identity rotation/onboarding:

```text
BLOCKED - FROZEN CONTRACT CONFLICT
```

If checkpoint contains unrelated or unsafe work that cannot be separated safely:

```text
BLOCKED - CHECKPOINT WORKTREE CONFLICT
```

If a real secret is found:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

Do not begin `003-03` inside this prompt.

---

## Главное правило этапа

`003-02` реализует только одну бизнес-границу:

```text
PRIVATE MAX identity
    ->
KVC user identity
```

с тремя допустимыми исходами:

```text
resolve existing
safe rotate existing chat binding
atomically onboard new user
```

и двумя классами ошибки:

```text
IdentityConflict
PersistenceConflict
```

Всё, что относится к token encryption, Kaiten credential lifecycle, bot transport, LLM/STT, dialog context или notifications delivery, остаётся вне этого этапа.
