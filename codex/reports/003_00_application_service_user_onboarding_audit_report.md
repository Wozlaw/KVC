# 003-00 - Application service user onboarding audit report

## Executive summary

Audited the current codebase and accepted branch `002` persistence contracts to define the application-service contracts for user onboarding, MAX identity binding, Kaiten connection lifecycle, token encryption boundaries, notification-settings creation, transaction ownership, DTOs, ports, and errors.

This was an audit-only task. No production code, tests, migrations, dependencies, environment files, branch switch, commit, Kaiten/MAX/GigaChat/STT calls, or schema changes were performed.

Recommended implementation branch:

```text
003-application-service-user-onboarding
```

Recommended status:

```text
READY WITH DECISIONS REQUIRED
```

## Scope

In scope:

```text
application/service layer above repositories and below transports/adapters
MAX private identity to KVC user binding
user lifecycle semantics
Kaiten connection lifecycle semantics
plaintext token boundary and encryption/decryption service contract
default notification settings creation
transaction orchestration
application DTO, port, and error taxonomy
concurrency and idempotency risks
```

Out of scope:

```text
implementation code
tests
migrations
schema changes
dependency changes
branch creation
Git commits
live external service mutations or probes
```

## Current repository state

Current branch at audit start:

```text
002-mvp-service-data-model
```

Recent history:

```text
568a0bb (HEAD -> 002-mvp-service-data-model) docs: close MVP service data model branch
4abdb91 feat: add persistence repository contracts
9cd4f91 feat: add MVP service persistence model
0501ca3 (main) feat: add PostgreSQL persistence foundation
4e4d728 chore: bootstrap Kaiten Voice Control project
```

Initial worktree:

```text
?? codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
```

The prompt file was already present as untracked input. This report is the only file created by the audit.

## Inputs reviewed

Reviewed:

```text
codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
codex/reports/002_00_mvp_service_data_model_audit_report.md
codex/reports/002_00a_mvp_service_data_model_final_specification.md
codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
codex/reports/002_01_mvp_service_data_model_implementation_report.md
codex/reports/002_02_live_postgresql_persistence_acceptance_report.md
codex/reports/002_03_repository_query_contracts_implementation_report.md
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
docs/specifications/Kaiten Voice Control — спецификация MVP v0.1.md
pyproject.toml
src/
tests/
```

Relevant existing packages:

```text
kvc_api
kvc_application
kvc_domain
kvc_persistence
kvc_notifications
kvc_config
kvc_integrations
kvc_worker
```

`kvc_application` and `kvc_domain` currently contain only package placeholders. The accepted concrete behavior is in `kvc_persistence`.

## Frozen persistence baseline

Branch `002` fixed the first KVC-owned service schema:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

Frozen constraints relevant to this audit:

```text
MAX scope is PRIVATE only.
One KVC user has one primary MAX private binding.
One KVC user has at most one Kaiten connection.
Kaiten content is not persistently copied into KVC DB.
Kaiten connection token is stored only as encrypted_api_token BYTEA plus token_encryption_version.
notification_settings defaults are enabled=false, due_soon_days=1, timezone='UTC'.
notification_history uses due_at TIMESTAMPTZ and due_date_time_present BOOLEAN.
notification_history has no due_date column.
notification dedup key is user_id, kaiten_card_id, due_at, due_date_time_present, notification_type.
```

Date-only notification recovery remains the accepted `002-00c` rule: when `due_date_time_present=false`, recover the selected date from the UTC date component of `due_at`, not by converting `due_at` through the user's timezone.

## Existing repository contracts

Repositories are async SQLAlchemy primitives with caller-owned transactions:

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

Confirmed design:

```text
repositories receive AsyncSession
repositories do not commit
repositories do not rollback
application/service layer must own transaction boundaries
selected read paths support FOR UPDATE where already specified
repositories contain no HTTP calls
repositories contain no encryption implementation
repositories contain no provider SDK bindings
```

## Service boundary

Recommended package shape for branch `003`:

```text
src/kvc_application/dto.py
src/kvc_application/errors.py
src/kvc_application/ports.py
src/kvc_application/services/identity.py
src/kvc_application/services/kaiten_connection.py
```

Acceptable variation: keep DTOs/errors next to services while the layer is small, as long as provider-specific code remains outside `kvc_application`.

The application layer may depend on:

```text
Python standard library
typed application DTOs/errors/ports
SQLAlchemy AsyncSession/sessionmaker types
kvc_persistence repositories and ORM entities returned by those repositories
```

The application layer must not depend on:

```text
Kaiten SDK/client implementation
MAX SDK/client implementation
GigaChat SDK/client implementation
SaluteSpeech SDK/client implementation
HTTP client details for providers
secrets loaded directly from .env
```

Provider adapters should implement application ports under `kvc_integrations`.

## Proposed application services

Recommended minimal services:

```text
IdentityService
KaitenConnectionService
```

Avoid one service per table. These two services map to actual workflows:

```text
IdentityService resolves or creates the KVC user identity from incoming MAX private metadata.
KaitenConnectionService manages verified encrypted Kaiten credentials and connection status.
```

Future command-processing services should build on these contracts instead of bypassing them.

## Identity service contract

Recommended primary method:

```python
async def resolve_or_onboard_private_max_user(
    input: ResolveMaxIdentityInput,
) -> IdentityResolution: ...
```

Required input fields:

```text
max_user_id: str
max_chat_id: str
chat_type: Literal["PRIVATE"]
```

Recommended output fields:

```text
user_id: UUID
max_chat_binding_id: UUID
user_status: Literal["ACTIVE", "DISABLED"]
is_new_user: bool
kaiten_connection_status: Literal["ACTIVE", "DISABLED", "NEEDS_REAUTH"] | None
```

The method should be idempotent for repeated messages from the same MAX private chat/user pair.

## MAX identity binding semantics

Recommended binding rule:

```text
max_chat_id routes the incoming private chat.
max_user_id is cross-checked to prevent account mix-ups.
```

Resolution order:

```text
1. Lookup max_chat_id.
2. If found, require max_user_id to match the binding.
3. If not found, lookup private binding by max_user_id.
4. If neither exists, create a new KVC user, primary private MAX binding, and default notification settings.
5. If max_chat_id and max_user_id point to different users, raise IdentityConflict.
```

Recommended user decision: auto-create the KVC user on the first incoming private MAX message. This matches the MVP because MAX private chat is the only user interface before Kaiten is connected.

## MAX chat rotation gap

Current `MaxChatRepository` can create and lookup bindings, but it has no explicit lock/update method for this case:

```text
same max_user_id
new max_chat_id
old max_chat_id no longer used by MAX
```

Recommended next implementation decision:

```text
Add a narrow repository method to lock/update the existing private binding's max_chat_id, or explicitly treat changed max_chat_id as a conflict requiring manual rebind.
```

Preferred behavior for MVP:

```text
Auto-update max_chat_id only when max_user_id already belongs to the same user and the new max_chat_id is not bound to another user.
Otherwise raise IdentityConflict.
```

This requires no schema change, only a small repository-contract extension.

## User lifecycle

Accepted states:

```text
ACTIVE
DISABLED
```

Recommended semantics:

```text
ACTIVE users can onboard, bind Kaiten, run explicit Kaiten commands, and receive enabled notifications.
DISABLED users remain resolvable by MAX identity but user-facing commands are blocked.
DISABLED users should not receive background notifications.
DISABLED users should not have their Kaiten connection changed by user-facing flows unless an explicit administrative re-enable operation exists.
```

No deletion workflow should be introduced in branch `003`.

## Notification settings creation

Recommended behavior:

```text
Create notification_settings eagerly during first MAX onboarding in the same transaction as user and max_chats creation.
```

Reasoning:

```text
defaults are already frozen and safe
enabled=false prevents surprise notifications
eager creation avoids later missing-settings branches
get_for_user can remain a pure read
get_or_create_for_user remains an explicit service action
```

This is a user/product decision to approve before implementation.

## Kaiten connection service contract

Recommended public operations:

```python
async def bind_or_replace_connection(
    input: BindKaitenConnectionInput,
) -> KaitenConnectionResult: ...
async def disable_connection(user_id: UUID) -> KaitenConnectionResult: ...
async def mark_needs_reauth(user_id: UUID, reason: str) -> None: ...
async def get_active_connection_secret(user_id: UUID) -> ActiveKaitenConnectionSecret: ...
```

`get_active_connection_secret` should be used only by application workflows that are about to call Kaiten through a port. It should not be exposed to transports as a DTO.

Recommended output fields for non-secret results:

```text
connection_id: UUID
user_id: UUID
status: Literal["ACTIVE", "DISABLED", "NEEDS_REAUTH"]
api_base_url: str
kaiten_user_id: str | None
workspace_id: str | None
last_verified_at: datetime | None
```

No output DTO should include plaintext token, encrypted token bytes, or encryption key metadata beyond the non-secret status.

## Kaiten connection lifecycle

Recommended lifecycle:

```text
missing -> ACTIVE after successful credential verification and encrypted persistence
ACTIVE -> ACTIVE after successful explicit token/base-url replacement
ACTIVE -> NEEDS_REAUTH after verified authentication failure from Kaiten
ACTIVE -> DISABLED after explicit user/admin disable command
NEEDS_REAUTH -> ACTIVE after successful explicit rebind
DISABLED -> ACTIVE only through explicit re-enable/rebind decision
```

Do not create a new application status outside the frozen persistence values unless a later specification changes the schema.

## Token verification-before-persist

Recommended policy:

```text
Verify plaintext Kaiten credentials before storing them as ACTIVE.
Do not persist invalid credentials.
Do not replace a previously valid ACTIVE token when Kaiten verification is temporarily unavailable.
Return a retryable application error for transient verification failures.
```

Because the frozen schema does not include `UNVERIFIED`, storing an unverified token would overload `NEEDS_REAUTH` or `ACTIVE` and weaken the service contract.

## External-call and transaction ordering

Recommended successful bind/replace flow:

```text
1. Validate input shape at the transport/API boundary.
2. Application service receives plaintext token as a short-lived value.
3. Verify token through KaitenCredentialVerifier outside a DB transaction.
4. Encrypt token through TokenCipher.
5. Open a short DB transaction.
6. Lock the user row and existing Kaiten connection row when present.
7. Re-check user status.
8. Create or update kaiten_connections as ACTIVE with last_verified_at.
9. Commit by leaving session.begin().
10. Return non-secret result DTO.
```

Do not hold a row lock while waiting on the Kaiten network call.

## Token encryption boundary

Allowed to see plaintext token:

```text
transport handler while receiving the user's explicit token message
application service method parameter with repr disabled
TokenCipher implementation
KaitenCredentialVerifier implementation
Kaiten adapter immediately before outbound API call
```

Not allowed to see plaintext token:

```text
repositories
ORM models as persisted plaintext
logs
reports
test snapshots
transport response DTOs
notification layer
worker scheduling state
```

The only persisted token representation remains:

```text
kaiten_connections.encrypted_api_token
kaiten_connections.token_encryption_version
```

## Encryption service contract

Recommended application port:

```python
@dataclass(frozen=True)
class EncryptedToken:
    ciphertext: bytes
    version: int


class TokenCipher(Protocol):
    def encrypt(self, plaintext: str) -> EncryptedToken: ...
    def decrypt(self, ciphertext: bytes, version: int) -> str: ...
```

Recommended implementation direction:

```text
Use the existing cryptography dependency.
Use authenticated encryption.
Keep key material outside PostgreSQL.
Load keys from environment or an external secret store through config/integration code.
Support versioned key rotation.
Never invent a custom cipher.
Never log plaintext, ciphertext, or key material.
```

For MVP, a small Fernet/MultiFernet-style adapter is acceptable if the implementation documents key format and rotation behavior. A later production hardening branch may replace the key source with KMS without changing the application port.

## Kaiten verifier port

Recommended application port:

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

The concrete implementation belongs in `kvc_integrations.kaiten`.

Adapter exceptions should be mapped to application errors at the port boundary:

```text
invalid credential -> KaitenAuthenticationFailed
temporary network/API outage -> KaitenTemporarilyUnavailable
unexpected provider response -> KaitenVerificationFailed
```

## Clock port

Recommended tiny port:

```python
class Clock(Protocol):
    def now(self) -> datetime: ...
```

Use it for:

```text
kaiten_connections.last_verified_at
future deterministic tests
future expiration workflows
```

The returned datetime should be timezone-aware UTC.

## DTO rules

Recommended DTO style:

```text
frozen dataclasses for application input/output DTOs
repr=False for fields containing plaintext tokens
no Pydantic dependency in application DTOs unless there is a clear local pattern
Pydantic schemas stay at API/transport boundaries
```

Suggested DTOs:

```text
ResolveMaxIdentityInput
IdentityResolution
BindKaitenConnectionInput
KaitenConnectionResult
ActiveKaitenConnectionSecret
KaitenCredentialVerification
EncryptedToken
```

`ActiveKaitenConnectionSecret` should be internal to application workflows and should not be returned to MAX/API transports.

## Error taxonomy

Recommended application errors:

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

User-facing mapping:

```text
IdentityConflict -> generic account binding conflict, operator review needed
UserDisabled -> account disabled
KaitenConnectionMissing -> ask user to connect Kaiten
KaitenConnectionDisabled -> ask user to enable/reconnect Kaiten
KaitenConnectionNeedsReauth -> ask user to reconnect Kaiten
KaitenAuthenticationFailed -> token rejected, ask for a valid token
KaitenTemporarilyUnavailable -> ask user to retry later
Credential* -> generic internal error, no secret details
PersistenceConflict -> retry once, then generic conflict
```

## Transaction orchestration

Recommended service construction:

```python
class IdentityService:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None: ...
```

Each write method owns:

```python
async with self._sessionmaker() as session:
    async with session.begin():
        ...
```

Repositories continue to receive the session and never commit or rollback.

Tests may inject a sessionmaker bound to a transactional fixture. Avoid hidden global sessions.

## Onboarding transaction flow

Recommended first-message onboarding transaction:

```text
1. Start session.begin().
2. Lookup MAX binding by max_chat_id.
3. Lookup private binding by max_user_id when needed.
4. If neither exists, create users row.
5. Create primary max_chats private binding.
6. Create notification_settings with defaults via get_or_create_for_user.
7. Read current Kaiten connection status if present.
8. Commit.
```

Unique constraints remain the final race guard. On `IntegrityError`, rollback and retry identity lookup once; if still inconsistent, raise `IdentityConflict` or `PersistenceConflict`.

## Kaiten bind transaction flow

Recommended bind/replace flow:

```text
1. Verify plaintext token outside the DB transaction.
2. Encrypt plaintext token.
3. Start session.begin().
4. Lock users row.
5. Reject DISABLED users.
6. Lock existing kaiten_connections row if present.
7. Create or update the single user connection as ACTIVE.
8. Set last_verified_at from Clock.now().
9. Commit.
```

If encryption fails, no DB transaction is needed. If DB persistence fails, plaintext token must not be logged while surfacing the error.

## Disabled-user behavior

Recommended guard:

```text
Identity resolution may return a DISABLED user.
All user-facing Kaiten operations must reject DISABLED users.
Kaiten connection bind/replace should reject DISABLED users unless an explicit admin path is added.
Background notification workflows must skip DISABLED users even when notification_settings.enabled=true.
```

Current `NotificationSettingsRepository.list_enabled()` does not filter by user status. Future notification application service or worker repository query must apply the disabled-user guard without changing branch `002` schema.

## Concurrency risks

First MAX message race:

```text
Two concurrent messages for the same new MAX identity can both try to create users/max_chats.
Use DB unique constraints, rollback, and retry lookup once.
```

Token replacement race:

```text
Verify outside locks, then serialize final write by locking user and connection.
For two explicit replacements, last committed verified token wins unless product chooses a stricter confirmation flow.
```

Reauth mark race:

```text
If an in-flight Kaiten call fails with 401 while a newer token has already been saved, avoid marking the newer connection NEEDS_REAUTH.
The mark_needs_reauth flow should lock and re-check that it is acting on the same connection/token version snapshot.
```

Disable race:

```text
Connection update flows should lock and re-check user.status so a disabled user cannot be reactivated by a concurrent bind transaction.
```

## Idempotency

Required idempotent outcomes:

```text
repeated MAX identity resolution for same max_user_id/max_chat_id returns same user
repeated notification settings creation returns existing row
repeated bind with same valid token/base-url produces one active connection row
repeated disable leaves connection DISABLED
mark_needs_reauth on already NEEDS_REAUTH remains safe
```

External Kaiten verification is not itself idempotent from KVC's point of view, so it should not occur inside a retrying DB transaction.

## Dependency injection

Recommended constructor dependencies:

```text
IdentityService:
  async_sessionmaker[AsyncSession]

KaitenConnectionService:
  async_sessionmaker[AsyncSession]
  KaitenCredentialVerifier
  TokenCipher
  Clock
```

Do not instantiate provider clients inside services. Composition belongs in API/worker startup or a dedicated dependency wiring module outside the application core.

## Integration boundaries

MAX integration:

```text
Transport parses inbound MAX update and passes max_user_id/max_chat_id/chat_type into IdentityService.
No MAX SDK object should enter application DTOs.
```

Kaiten integration:

```text
Adapter implements KaitenCredentialVerifier and future Kaiten command/query ports.
Application layer depends on the port, not on HTTP or SDK details.
```

LLM/STT integrations:

```text
They may normalize user input in future command flows.
They must not execute business operations directly.
They must not bypass application service authorization and explicit-command checks.
```

## Security notes

Security requirements for implementation:

```text
no plaintext token persistence
no token values in repr/logs/errors/reports
no key material in tracked files
.env remains untracked
.env.example may contain only empty or demonstration values
encrypted token bytes are not user-facing DTO data
application errors do not include provider request headers or auth details
```

Use `SecretStr` only at config/API boundaries if helpful. For application dataclasses, prefer `repr=False` on plaintext fields.

## Specification alignment

The proposed contracts preserve fixed requirements:

```text
Kaiten remains source of truth for project state.
KVC DB does not store a persistent local copy of Kaiten content.
Kaiten mutations require explicit user command.
Background worker may read Kaiten and send notifications, but must not mutate Kaiten.
MAX is the MVP user interface.
Each user connects their own Kaiten account.
Kaiten API token is stored encrypted.
```

No conflict with `docs/specifications/` requires a schema change for this stage.

## Required decisions before implementation

Decision 1:

```text
Should KVC auto-create a user on the first private MAX message?
Recommendation: yes.
```

Decision 2:

```text
Should notification_settings be created eagerly during onboarding?
Recommendation: yes, with enabled=false defaults.
```

Decision 3:

```text
Should Kaiten credentials be verified before persistence?
Recommendation: yes; do not persist invalid or unverifiable credentials as ACTIVE.
```

Decision 4:

```text
What is the MVP encryption/key strategy?
Recommendation: application TokenCipher port plus cryptography-based adapter using versioned environment/external-secret keys.
```

Decision 5:

```text
What happens when Kaiten verification is temporarily unavailable?
Recommendation: return retryable error and leave existing connection unchanged.
```

Decision 6:

```text
How should replacement of an existing Kaiten connection behave?
Recommendation: require explicit user command; last committed verified replacement wins under lock.
```

Decision 7:

```text
How should changed max_chat_id for the same max_user_id be handled?
Recommendation: auto-update only when it is unambiguously the same private MAX user; otherwise raise IdentityConflict.
```

## Recommended branch plan

Recommended next prompts:

```text
003_00a_application_service_user_onboarding_final_specification_prompt.md
003_01_application_service_contracts_implementation_prompt.md
003_02_identity_onboarding_service_implementation_prompt.md
003_03_token_cipher_contract_and_adapter_implementation_prompt.md
003_04_kaiten_connection_service_implementation_prompt.md
003_05_application_service_acceptance_prompt.md
003_06_branch_acceptance_git_integration_closeout_prompt.md
```

The `003_00a` specification step is recommended because this audit leaves explicit user/product decisions open.

## Files created or changed

Created:

```text
codex/reports/003_00_application_service_user_onboarding_audit_report.md
```

No production files, tests, migrations, dependency files, or environment files were changed.

## Checks performed

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
61 passed in 4.39s

.venv\Scripts\python.exe -m pytest -W error
61 passed in 4.15s

.venv\Scripts\python.exe -m ruff format --check .
74 files already formatted

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
```

Post-report verification:

```text
.venv\Scripts\python.exe -m ruff format --check .
75 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

git diff --check
<no output, exit code 0>

git status --short
?? codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
?? codex/reports/003_00_application_service_user_onboarding_audit_report.md
```

## Notes and risks

Open risks:

```text
MAX chat rotation handling is not covered by current repository write methods.
Notification worker must remember to filter disabled users because list_enabled returns settings only.
mark_needs_reauth needs stale-token protection to avoid downgrading a freshly replaced token.
Final encryption adapter details must be specified before implementation.
Transient Kaiten outage behavior must be approved before user-facing onboarding copy is written.
```

These risks do not block the audit, but they should be resolved in `003_00a` before implementation.

## Final stage status

```text
READY WITH DECISIONS REQUIRED
```

The audit is complete. The codebase is ready for a final specification prompt that freezes the open decisions before implementation begins.
