# 003-00a - Application service and user onboarding final specification

## 1. Executive summary

This document freezes the branch `003` application-service contract for MAX private identity onboarding and Kaiten credential lifecycle.

The contract is ready for direct implementation in `003-01` through `003-04` without another architecture decision pass.

Final status:

```text
ACCEPTED SPECIFICATION - READY FOR 003-01
```

No production code, tests, migrations, dependencies, environment files, branches, commits, live Kaiten calls, live MAX calls, or database DDL/DML were introduced by this stage.

## 2. Accepted user decisions

The following decisions are frozen for branch `003`:

| Decision | Final contract |
|---|---|
| Automatic first-message onboarding | A new KVC user is created automatically on the first private MAX message when the MAX identity is unknown. |
| Eager notification settings | `notification_settings` is created in the same transaction as the new user and MAX binding. |
| Verify before persistence | Kaiten credentials are verified before encryption and persistence as `ACTIVE`. Invalid or transiently unverifiable credentials are not stored as active credentials. |
| TokenCipher and versioned external keys | `kvc_application` depends on `TokenCipher`; the concrete adapter uses authenticated encryption, versioned key support, and key material outside PostgreSQL/Git. |
| Transient Kaiten verification outage | Return a retryable application error and leave any existing connection unchanged. |
| Explicit connection replacement | Existing Kaiten credential/base URL replacement requires an explicit user command. Concurrent successful replacements use last-committed verified write wins. |
| MAX chat rotation | Same `max_user_id` with a new `max_chat_id` is auto-updated only when unambiguous and conflict-free; otherwise raise `IdentityConflict`. |

These choices must not be reopened during `003-01...003-04`.

## 3. Frozen persistence/repository baseline

The accepted branch `002` persistence baseline contains exactly seven KVC-owned business tables:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

Alembic head:

```text
00201_mvp_service_model
```

Frozen invariants:

```text
MAX scope is PRIVATE only.
One KVC user has one primary MAX private binding.
One KVC user has at most one Kaiten connection.
Kaiten content is not persistently copied into KVC DB.
Plaintext Kaiten token is never persisted.
kaiten_connections stores encrypted_api_token BYTEA and token_encryption_version.
notification_settings defaults are enabled=false, due_soon_days=1, timezone='UTC'.
notification_history stores due_at TIMESTAMPTZ and due_date_time_present BOOLEAN.
notification_history has no due_date column.
```

Repository baseline:

```text
repositories receive AsyncSession
repositories do not commit
repositories do not rollback
application/service layer owns transactions
repositories contain no provider HTTP/SDK code
repositories contain no encryption implementation
```

## 4. Layer/dependency contract

Final dependency direction:

```text
transport
(MAX bot / future HTTP endpoints)
        |
        v
kvc_application
        |
        v
application ports + kvc_persistence repositories
        |
        v
kvc_persistence
        |
        v
SQLAlchemy / PostgreSQL
```

External systems are adapters:

```text
Kaiten
MAX
GigaChat
SaluteSpeech
future KMS/secret provider
```

`kvc_application` may depend on:

```text
Python standard library
application DTOs
application errors
application Protocol ports
SQLAlchemy AsyncSession / async_sessionmaker types
kvc_persistence repositories
ORM entities returned by repository contracts
```

`kvc_application` must not depend on:

```text
Kaiten HTTP/client implementation
MAX SDK/client implementation
GigaChat SDK/client implementation
SaluteSpeech SDK/client implementation
provider-specific request/response objects
direct .env access
direct settings loading inside business service methods
secret-key loading inside application services
provider auth headers
transport schemas as application contracts
```

Do not introduce a domain abstraction layer only for formal layering if it carries no behavior.

## 5. Final service inventory

Branch `003` has two application services:

```text
IdentityService
KaitenConnectionService
```

`IdentityService` owns:

```text
MAX private identity resolution
first-message KVC user onboarding
MAX binding conflict detection
safe MAX chat rotation
default notification settings creation
user lifecycle visibility during identity resolution
```

`KaitenConnectionService` owns:

```text
verified bind
verified replacement
disable
NEEDS_REAUTH lifecycle
secure credential retrieval for internal workflows
disabled-user guard
transaction orchestration around connection state
```

Do not create one service per table.

## 6. IdentityService contract

Public operation:

```python
async def resolve_or_onboard_private_max_user(
    input: ResolveMaxIdentityInput,
) -> IdentityResolution: ...
```

Input:

```text
max_user_id: str
max_chat_id: str
chat_type: Literal["PRIVATE"]
```

Output:

```text
user_id: UUID
max_chat_binding_id: UUID
user_status: Literal["ACTIVE", "DISABLED"]
is_new_user: bool
kaiten_connection_status: Literal["ACTIVE", "DISABLED", "NEEDS_REAUTH"] | None
```

The output must not expose ORM/session objects.

The operation is idempotent for the same `max_user_id + max_chat_id`.

## 7. MAX identity resolution algorithm

Final algorithm:

```text
1. Start a DB transaction.
2. Lookup binding by incoming max_chat_id.
3. If found, require binding.max_user_id == incoming max_user_id.
4. If max_chat_id is not found, lookup PRIVATE binding by max_user_id.
5. If max_user_id binding is found, execute safe MAX chat rotation.
6. If neither binding exists, create a KVC user.
7. Create a primary PRIVATE MAX binding for the new user.
8. Create notification_settings defaults for the new user.
9. Read current Kaiten connection status if a connection exists.
10. Commit.
11. Return IdentityResolution.
```

Conflict:

```text
max_chat_id points to user A
max_user_id points to user B
```

Result:

```text
IdentityConflict
```

No automatic identity merge is allowed.

## 8. MAX chat rotation contract

Safe rotation applies only to this case:

```text
existing PRIVATE binding by max_user_id
incoming max_chat_id differs
incoming max_chat_id is unbound
same KVC user
```

Required flow:

```text
1. Lock the existing PRIVATE binding for max_user_id.
2. Re-check that binding.user_id is unchanged.
3. Re-check that binding.chat_type == 'PRIVATE'.
4. Re-check that incoming max_chat_id is not bound to another user.
5. Update binding.max_chat_id.
6. Preserve one primary binding semantics.
```

Forbidden:

```text
steal max_chat_id from another user
merge two KVC users
create a second primary binding accidentally
ignore max_user_id mismatch
rotate group chat identity
```

Future implementation may add a narrow `MaxChatRepository` lock/update method. No schema migration is required.

## 9. User lifecycle and disabled-user matrix

Frozen user states:

```text
ACTIVE
DISABLED
```

| Operation | ACTIVE | DISABLED |
|---|---:|---:|
| resolve identity | allow | allow and return `DISABLED` |
| onboard new identity | allow | n/a |
| rotate MAX chat | allow | allow identity-safe rotation only; no business re-enable |
| bind Kaiten | allow | reject with `UserDisabled` |
| replace Kaiten | allow | reject with `UserDisabled` |
| disable Kaiten | allow, idempotent | allow as idempotent no-op/status operation |
| get active secret for command | allow if connection is `ACTIVE` | reject with `UserDisabled` |
| execute Kaiten command | allow with active connection | reject with `UserDisabled` |
| send notification | allow if settings enabled | skip |

No deletion workflow and no administrative re-enable path are part of branch `003`.

## 10. Notification settings onboarding contract

On first-message onboarding, these rows are created in one DB transaction:

```text
users
max_chats
notification_settings
```

`notification_settings` values:

```text
enabled = false
due_soon_days = 1
timezone = UTC
```

The `enabled=false` default prevents surprise notifications. Repeated resolution after a concurrency retry must return the existing user/settings row, not create duplicates.

Notification worker implementation is out of scope for branch `003`, but future worker/application notification flow must filter `users.status == 'ACTIVE'`.

## 11. KaitenConnectionService contract

Public operations:

```python
async def bind_or_replace_connection(
    input: BindKaitenConnectionInput,
) -> KaitenConnectionResult: ...


async def disable_connection(
    user_id: UUID,
) -> KaitenConnectionResult: ...


async def mark_needs_reauth(
    input: MarkKaitenNeedsReauthInput,
) -> KaitenConnectionResult | None: ...


async def get_active_connection_secret(
    user_id: UUID,
) -> ActiveKaitenConnectionSecret: ...
```

`bind_or_replace_connection` is used for first bind and explicit replacement.

`get_active_connection_secret` is internal application API only. It must not be used as a transport response DTO.

## 12. Kaiten connection state machine

Frozen states:

```text
ACTIVE
DISABLED
NEEDS_REAUTH
```

Allowed transitions:

| From | To | Cause |
|---|---|---|
| missing | ACTIVE | successful verified first bind |
| ACTIVE | ACTIVE | successful explicit verified replacement |
| ACTIVE | NEEDS_REAUTH | confirmed auth failure for the same credential snapshot |
| ACTIVE | DISABLED | explicit disable |
| NEEDS_REAUTH | ACTIVE | successful explicit verified rebind |
| NEEDS_REAUTH | DISABLED | explicit disable |
| DISABLED | ACTIVE | explicit verified rebind/re-enable action |
| DISABLED | DISABLED | repeated disable |
| NEEDS_REAUTH | NEEDS_REAUTH | repeated same-snapshot auth failure |

No new persistence status is allowed in branch `003`.

## 13. Verification-before-persist contract

Successful bind/replace ordering:

```text
1. Transport validates outer input shape.
2. Application receives plaintext token as a short-lived secret value.
3. Application checks user existence/status without holding a long DB lock.
4. KaitenCredentialVerifier verifies the credential outside DB row locks.
5. TokenCipher encrypts the token.
6. Application opens a short DB transaction.
7. Application locks the user row.
8. Application re-checks user.status == 'ACTIVE'.
9. Application locks the existing kaiten_connections row if present.
10. Application creates or updates the connection.
11. Application sets status = 'ACTIVE'.
12. Application persists ciphertext and token_encryption_version.
13. Application sets last_verified_at = Clock.now().
14. Transaction commits.
15. Service returns a non-secret DTO.
```

Invalid token:

```text
raise KaitenAuthenticationFailed
do not persist token
leave existing connection unchanged
```

Transient Kaiten outage:

```text
raise KaitenTemporarilyUnavailable
do not persist token
leave existing connection unchanged
```

## 14. Token plaintext/security boundary

Plaintext token may exist only in:

```text
transport input handling
BindKaitenConnectionInput with repr disabled
KaitenConnectionService short-lived local variables
KaitenCredentialVerifier adapter
TokenCipher adapter
internal Kaiten adapter immediately before authenticated outbound call
ActiveKaitenConnectionSecret with repr disabled
```

Plaintext token must not exist in:

```text
repositories
ORM persisted fields
logs
repr output
exceptions
reports
snapshots/golden files
transport output DTOs
notification layer
worker scheduling state
database diagnostics
```

Allowed safe logging:

```text
user_id
max_chat_binding_id
connection_id
status transition
safe provider status class
application error type
operation name
```

Forbidden logging:

```text
plaintext token
encrypted_api_token
crypto key
Authorization header
secret config values
full provider response containing auth material
full secret-bearing URL
```

## 15. DTO contracts

Use frozen dataclasses for application DTOs. Do not use Pydantic DTOs in `kvc_application` unless a future concrete need appears.

`ResolveMaxIdentityInput`:

```text
max_user_id: str
max_chat_id: str
chat_type: Literal["PRIVATE"]
```

`IdentityResolution`:

```text
user_id: UUID
max_chat_binding_id: UUID
user_status: Literal["ACTIVE", "DISABLED"]
is_new_user: bool
kaiten_connection_status: Literal["ACTIVE", "DISABLED", "NEEDS_REAUTH"] | None
```

`BindKaitenConnectionInput`:

```text
user_id: UUID
api_base_url: str
plaintext_token: str with field(repr=False)
```

`KaitenConnectionResult`:

```text
connection_id: UUID
user_id: UUID
status: Literal["ACTIVE", "DISABLED", "NEEDS_REAUTH"]
api_base_url: str
kaiten_user_id: str | None
workspace_id: str | None
last_verified_at: datetime | None
```

`KaitenCredentialSnapshot`:

```text
connection_id: UUID
encrypted_api_token: bytes with field(repr=False)
token_encryption_version: int
```

`ActiveKaitenConnectionSecret`:

```text
connection_id: UUID
user_id: UUID
api_base_url: str
plaintext_token: str with field(repr=False)
snapshot: KaitenCredentialSnapshot with repr disabled
```

`MarkKaitenNeedsReauthInput`:

```text
user_id: UUID
snapshot: KaitenCredentialSnapshot
reason: str
```

`KaitenCredentialVerification`:

```text
kaiten_user_id: str | None
workspace_id: str | None
```

`EncryptedToken`:

```text
ciphertext: bytes
version: int
```

Public output DTOs must not include plaintext token, ciphertext, encryption keys, or Authorization data.

## 16. Port contracts

`TokenCipher`:

```python
@dataclass(frozen=True)
class EncryptedToken:
    ciphertext: bytes
    version: int


class TokenCipher(Protocol):
    def encrypt(self, plaintext: str) -> EncryptedToken: ...

    def decrypt(self, ciphertext: bytes, version: int) -> str: ...
```

`KaitenCredentialVerifier`:

```python
@dataclass(frozen=True)
class KaitenCredentialVerification:
    kaiten_user_id: str | None
    workspace_id: str | None


class KaitenCredentialVerifier(Protocol):
    async def verify(
        self,
        *,
        api_base_url: str,
        plaintext_token: str,
    ) -> KaitenCredentialVerification: ...
```

`Clock`:

```python
class Clock(Protocol):
    def now(self) -> datetime: ...
```

`Clock.now()` returns timezone-aware UTC.

Do not add a port for every helper function.

## 17. Crypto/key-version contract

The concrete crypto adapter is not implemented in `003-00a`, but its contract is frozen:

```text
uses existing cryptography dependency
uses authenticated encryption
supports a versioned key ring
has one active write key/version
can decrypt old versions during key rotation
loads key material outside kvc_application
does not store key material in PostgreSQL
does not store key material in Git
does not log plaintext, ciphertext, or key material
```

`token_encryption_version` means:

```text
crypto/key version
```

It must not be used as a logical credential revision.

MVP adapter shape may use Fernet/MultiFernet if the implementation preserves the `TokenCipher` API and future KMS/secret-manager replacement does not require changing application services.

## 18. Stale-credential snapshot contract

Problem:

```text
T1 reads credential A and calls Kaiten.
T2 replaces credential A with B and connection remains ACTIVE.
T1 receives 401 for A.
T1 must not mark credential B as NEEDS_REAUTH.
```

Frozen MVP snapshot identifier:

```text
connection_id
encrypted_api_token
token_encryption_version
```

Rationale:

```text
connection_id anchors the single user connection row.
encrypted_api_token distinguishes the stored credential bytes.
token_encryption_version distinguishes the crypto key/version used for those bytes.
```

`token_encryption_version` alone is insufficient because multiple different plaintext tokens can use the same crypto version.

The snapshot is internal only. It must not cross a transport response boundary and must not be logged.

No schema migration is required for stale-credential protection.

## 19. mark_needs_reauth algorithm

`get_active_connection_secret` flow:

```text
1. Open a short DB transaction.
2. Lock user row and reject DISABLED users.
3. Lock kaiten_connections row for the user.
4. Require connection.status == 'ACTIVE'.
5. Capture snapshot = connection_id + encrypted_api_token + token_encryption_version.
6. Decrypt encrypted_api_token through TokenCipher.
7. Return ActiveKaitenConnectionSecret internally.
8. Commit/release lock before the external Kaiten call.
```

`mark_needs_reauth` flow after an auth failure:

```text
1. Open a short DB transaction.
2. Lock the current kaiten_connections row for user_id.
3. If no row exists, return None.
4. Compare current connection_id, encrypted_api_token, and token_encryption_version with input.snapshot.
5. If snapshot differs, treat as stale failure and return None without state change.
6. If status == 'DISABLED', return current result without state change.
7. If status == 'NEEDS_REAUTH', return current result idempotently.
8. If status == 'ACTIVE' and snapshot matches, set status = 'NEEDS_REAUTH'.
9. Commit and return KaitenConnectionResult.
```

This compare-and-mark contract is implementable using current model fields and the existing `KaitenConnectionRepository.get_for_user_for_update()` path. A narrow repository helper may be added later only to reduce duplication, not because the schema is insufficient.

## 20. External-call and DB-transaction matrix

| Use case | External call | DB transaction | Row lock | Ordering | Failure behavior |
|---|---|---|---|---|---|
| resolve existing MAX identity | none | yes, read/resolve transaction | lock only if rotation/update is needed | lookup by chat, cross-check user | mismatch -> `IdentityConflict` |
| first-message onboarding | none | yes | user/settings rows created in one transaction; unique constraints guard races | create user, MAX binding, settings, then read connection status | unique race -> rollback and retry lookup once |
| MAX chat rotation | none | yes | lock existing private binding; re-check incoming chat unbound | lock/re-check/update | conflict -> `IdentityConflict` |
| first Kaiten bind | Kaiten credential verification | yes after external call | lock user; lock connection if exists | verify, encrypt, short transaction persist | invalid -> no persist; transient outage -> no persist |
| Kaiten replacement | Kaiten credential verification | yes after external call | lock user and existing connection | explicit command, verify, encrypt, lock, write | last committed verified replacement wins |
| disable connection | none | yes | lock user and connection when present | re-check user, set `DISABLED` or return idempotent result | missing -> `KaitenConnectionMissing` unless future admin semantics differ |
| get active secret | decrypt only, no provider network | yes | lock user and connection while snapshot is captured | lock, validate ACTIVE, capture snapshot, decrypt | disabled/missing/non-active/decrypt failure -> application error |
| mark NEEDS_REAUTH | none | yes | lock connection | compare snapshot, then update only if current ACTIVE | stale snapshot -> no-op; disabled -> no-op; missing -> None |

General rule:

```text
external network call outside DB row-lock wait
short transaction for final state transition
re-check mutable guards under lock
```

## 21. Transaction ownership

Frozen rule:

```text
repositories do not own commit/rollback
application write method owns transaction boundary
```

Service construction:

```python
class IdentityService:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None: ...


class KaitenConnectionService:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        verifier: KaitenCredentialVerifier,
        token_cipher: TokenCipher,
        clock: Clock,
    ) -> None: ...
```

Write methods use:

```python
async with self._sessionmaker() as session:
    async with session.begin():
        ...
```

Do not add hidden global sessions. Do not add a UnitOfWork abstraction in branch `003`.

## 22. Concurrency invariants

First MAX message race:

```text
Two concurrent messages may both observe missing MAX identity.
One transaction wins the UNIQUE constraints.
The loser rolls back and retries identity lookup once.
Both requests must ultimately resolve to the same KVC user or surface IdentityConflict/PersistenceConflict.
No infinite retry loop.
```

MAX rotation race:

```text
The implementation locks the existing max_user_id binding.
It re-checks that incoming max_chat_id is unbound before update.
It never steals a chat binding from another user.
```

Token replacement race:

```text
Each credential verification occurs outside row locks.
Final persistence locks user and connection.
Last committed verified replacement wins.
```

Disable race:

```text
Connection update flows lock and re-check user.status.
A disabled user cannot be reactivated by a concurrent user-facing bind transaction.
```

Stale auth failure race:

```text
mark_needs_reauth changes status only for the same captured credential snapshot.
```

## 23. Idempotency contract

Required idempotent outcomes:

```text
same max_user_id + max_chat_id -> same KVC user
repeated eager settings creation -> one notification_settings row
safe repeated MAX rotation request -> same final binding
repeated verified bind of same logical credential/base URL -> one ACTIVE connection row
repeated disable -> DISABLED
repeated mark_needs_reauth for same current credential -> NEEDS_REAUTH
stale mark_needs_reauth for replaced credential -> no-op
```

No global idempotency-key subsystem is required in branch `003`.

## 24. Error taxonomy

Application-level hierarchy:

```text
ApplicationError
IdentityConflict
UserDisabled
KaitenConnectionMissing
KaitenConnectionDisabled
KaitenConnectionNeedsReauth
KaitenAuthenticationFailed
KaitenTemporarilyUnavailable
KaitenVerificationFailed
CredentialEncryptionFailed
CredentialDecryptionFailed
PersistenceConflict
```

No broader taxonomy is needed for branch `003`.

## 25. Provider/persistence error mapping

Provider mapping at Kaiten adapter/application boundary:

```text
credential rejected / 401-style auth failure -> KaitenAuthenticationFailed
temporary timeout/network/5xx-like availability failure -> KaitenTemporarilyUnavailable
unexpected response/protocol violation -> KaitenVerificationFailed
```

Application errors must not contain:

```text
token
Authorization header
ciphertext
key material
raw provider body with secrets
full secret-bearing URL
```

Persistence mapping:

```text
known identity uniqueness conflict -> IdentityConflict
known retryable onboarding race -> retry once, then resolved result or PersistenceConflict
unexpected persistence invariant failure -> PersistenceConflict
raw SQLAlchemy errors do not cross transport boundary as user-facing errors
programming errors are not hidden behind generic retry loops
```

## 26. Dependency injection/composition root

`kvc_application` must not load `.env` or construct provider clients inside service methods.

Composition root may be:

```text
API startup
worker startup
dedicated dependency wiring module
```

Composition root may:

```text
load AppSettings
construct AsyncEngine and async_sessionmaker
construct TokenCipher adapter
construct KaitenCredentialVerifier adapter
construct Clock
construct application services
```

Provider-specific code remains in `kvc_integrations`.

## 27. Repository extensions required by future implementation

Required for `003-02`:

```text
MaxChatRepository:
    get_private_by_max_user_id_for_update(max_user_id: str) -> MaxChat | None
    update_max_chat_id(binding: MaxChat, max_chat_id: str) -> MaxChat
```

These are narrow lock/update primitives for safe MAX chat rotation. They do not require schema changes.

Not required for stale credential flow:

```text
new schema column
logical credential revision
new Alembic migration
```

Existing `KaitenConnectionRepository.get_for_user_for_update()` is sufficient for compare-and-mark. A later narrow helper may be added only to centralize assignment, not to change semantics.

## 28. Future testing matrix

Unit tests:

```text
existing identity
new identity onboarding
disabled identity
identity conflict
safe MAX rotation
unsafe MAX rotation
default settings creation
Kaiten bind success
invalid token
temporary verification failure
encryption failure
replacement
disable
missing connection
disabled connection
NEEDS_REAUTH connection
decrypt failure
stale mark_needs_reauth no-op
current credential auth failure -> NEEDS_REAUTH
```

PostgreSQL integration tests:

```text
concurrent first-message onboarding
MAX uniqueness race
MAX rotation locking
single Kaiten connection invariant
concurrent replacements
disabled-user re-check under lock
stale credential race
transaction rollback behavior
```

Security tests:

```text
plaintext absent from DB
plaintext absent from repr
plaintext absent from logs/errors
ciphertext persisted
wrong encryption version/key fails safely
non-secret output DTO
```

## 29. Implementation-stage decomposition

Planned branch stages:

| Stage | Acceptance target |
|---|---|
| `003-00` audit | risks and decisions identified |
| `003-00a` final application service/user onboarding specification | frozen contract accepted |
| `003-01` application DTO/port/error contracts implementation | importable typed contracts, no service behavior |
| `003-02` IdentityService + MAX binding onboarding/rotation implementation | onboarding and rotation tests pass |
| `003-03` TokenCipher contract + cryptography adapter implementation | encryption/key-version tests pass |
| `003-04` KaitenConnectionService + credential lifecycle implementation | bind/replace/disable/secret/reauth tests pass |
| `003-05` full application service acceptance | unit and PostgreSQL integration acceptance pass |
| `003-06` branch acceptance / Git integration / closeout | branch organized and ready for next stage |

Each stage has one acceptance target. Hidden product decisions are not allowed in implementation stages.

## 30. Explicit out-of-scope list

Out of scope for `003-00a` and not implemented here:

```text
MAX bot polling/webhook implementation
MAX message text UX
Kaiten card/board command execution
GigaChat prompt/intent parsing
SaluteSpeech/STT
notification worker scheduling
full notification delivery flow
dialog resolver
PendingCommand orchestration
Kaiten content local cache
multi-Kaiten-account support
multi-workspace selector UX
group MAX chats
user deletion
admin UI
KMS integration
token rotation background job
distributed locks
outbox
schema migration
```

## 31. Consistency review

| Check | Result |
|---|---|
| Application layer does not depend on provider implementation | PASS |
| Repositories still do not commit/rollback | PASS |
| No schema changes | PASS |
| First-message onboarding atomically creates user, MAX binding, settings | PASS |
| `enabled=false` prevents surprise notifications | PASS |
| Identity resolution is idempotent | PASS |
| MAX rotation cannot steal another chat binding | PASS |
| Disabled user cannot rebind Kaiten via user-facing flow | PASS |
| Credential verification occurs before persistence | PASS |
| Transient Kaiten outage leaves existing ACTIVE connection unchanged | PASS |
| Plaintext token does not cross persistence boundary | PASS |
| Ciphertext/key material are absent from public DTOs | PASS |
| `token_encryption_version` is only crypto/key version | PASS |
| Stale auth failure cannot downgrade freshly replaced credential | PASS |
| `mark_needs_reauth` uses exact credential snapshot semantics | PASS |
| Network call does not run under long row lock | PASS |
| Concurrent replacements have clear winner semantics | PASS |
| Provider raw exceptions do not cross boundary | PASS |
| No local Kaiten content cache introduced | PASS |
| Implementation stages contain no hidden product decisions | PASS |

## 32. Changed files

Created:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
```

Formatted existing untracked prompt snippets so the mandatory `ruff format --check .` gate passes:

```text
codex/prompts/003_00a_application_service_user_onboarding_final_specification_prompt.md
```

No production code, tests, Alembic/schema, dependencies, configuration, or environment files were changed.

Change classification:

```text
Production code: none
Tests: none
Alembic/schema: none
Dependencies: none
Configuration: none
Documentation: codex/reports/003_00a_application_service_user_onboarding_final_specification.md
Prompts: codex/prompts/003_00a_application_service_user_onboarding_final_specification_prompt.md formatting only
Reports: codex/reports/003_00a_application_service_user_onboarding_final_specification.md
Other: none
```

## 33. Quality gate

Commands run:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
61 passed in 4.09s

.venv\Scripts\python.exe -m pytest -W error
61 passed in 4.34s

.venv\Scripts\python.exe -m ruff format --check .
initial result: failed on Python snippets inside codex/prompts/003_00a_application_service_user_onboarding_final_specification_prompt.md
final result: 76 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 33 source files

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.

git diff --check
<no output, exit code 0>

git branch --show-current
002-mvp-service-data-model

git status --short
?? codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
?? codex/prompts/003_00a_application_service_user_onboarding_final_specification_prompt.md
?? codex/reports/003_00_application_service_user_onboarding_audit_report.md

git diff --stat
<no output; current changes are untracked documentation/prompt artifacts>
```

Post-report verification:

```text
.venv\Scripts\python.exe -m ruff format --check .
77 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

git diff --check
<no output, exit code 0>

git status --short
?? codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
?? codex/prompts/003_00a_application_service_user_onboarding_final_specification_prompt.md
?? codex/reports/003_00_application_service_user_onboarding_audit_report.md
?? codex/reports/003_00a_application_service_user_onboarding_final_specification.md

git diff --stat
<no output; current changes are untracked documentation/prompt artifacts>
```

## 34. Final status

```text
ACCEPTED SPECIFICATION - READY FOR 003-01
```

Branch `003` can proceed to `003-01` as a pure DTO/port/error contract implementation stage.
