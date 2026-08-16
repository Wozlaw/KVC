# 003-04 — KaitenConnectionService, credential verifier and lifecycle implementation

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Функциональная ветка:

```text
003 — Application service layer and user onboarding
```

Текущая рабочая ветка:

```text
003-application-service-user-onboarding
```

Принятые этапы:

```text
003-00   Application service/user onboarding audit
003-00a  Final application service/user onboarding specification
003-01   Application DTO/port/error contracts implementation
003-02   IdentityService + MAX onboarding/rotation implementation
003-03   Versioned TokenCipher + crypto configuration implementation
```

Основные нормативные документы:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
codex/reports/002_03_repository_query_contracts_implementation_report.md
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

Финальный статус `003-03`:

```text
IMPLEMENTED - READY FOR 003-04 KAITEN CONNECTION SERVICE
```

Этот этап завершает application-service implementation ветки `003`.

На этом этапе необходимо:

1. создать checkpoint commit принятого `003-03`;
2. реализовать concrete `KaitenCredentialVerifier` HTTP adapter;
3. реализовать concrete UTC clock adapter;
4. реализовать `KaitenConnectionService`;
5. связать в service workflow:
   - credential verification;
   - `TokenCipher`;
   - caller-owned PostgreSQL transactions;
   - `kaiten_connections`;
6. реализовать:
   - first bind;
   - explicit verified replacement/re-enable;
   - disable;
   - secure active-secret retrieval;
   - stale-safe `mark_needs_reauth`;
7. доказать locking/concurrency/idempotency/security contracts тестами;
8. создать report `003-04`.

Не реализовывать MAX transport/bot, команды Kaiten-карточек, dialog resolver, notification worker, GigaChat/STT или production startup wiring transport layer.

---

# 1. Главная цель

После `003-04` должен существовать полностью реализованный application workflow:

```text
explicit user credential input
        ↓
BindKaitenConnectionInput
        ↓
KaitenConnectionService
        ↓
KaitenCredentialVerifier
        ↓
GET /api/latest/users/current
        ↓
verified identity
        ↓
TokenCipher.encrypt()
        ↓
short locked PostgreSQL transaction
        ↓
kaiten_connections
        ↓
ACTIVE
```

И internal command workflow:

```text
user_id
    ↓
get_active_connection_secret()
    ↓
decrypt stored token
    ↓
ActiveKaitenConnectionSecret
    ↓
future Kaiten command adapter call
```

И auth-failure workflow:

```text
command used credential snapshot A
        ↓
Kaiten auth failure
        ↓
mark_needs_reauth(snapshot A)
        ↓
compare against current persisted snapshot
        ↓
same snapshot:
    ACTIVE -> NEEDS_REAUTH

different snapshot:
    stale failure -> no-op
```

---

# 2. Источники истины и приоритет

Перед implementation обязательно изучи:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
codex/reports/002_03_repository_query_contracts_implementation_report.md
```

Также изучи фактический код:

```text
src/kvc_application/dto.py
src/kvc_application/errors.py
src/kvc_application/ports.py
src/kvc_application/services/
src/kvc_integrations/security/
src/kvc_integrations/kaiten/
src/kvc_config/
src/kvc_persistence/models.py
src/kvc_persistence/repositories/
src/kvc_persistence/session.py
tests/
pyproject.toml
.env.example
```

Приоритет:

```text
003-00a final frozen specification
    >
003-01 frozen application contracts
    >
003-03 accepted crypto contract
    >
003-02 accepted identity implementation
    >
002 accepted persistence/repository contracts
```

Не переоткрывать frozen decisions.

---

# 3. Frozen application contracts — не менять

Уже существуют:

```text
BindKaitenConnectionInput
KaitenConnectionResult
KaitenCredentialSnapshot
ActiveKaitenConnectionSecret
MarkKaitenNeedsReauthInput
KaitenCredentialVerification
EncryptedToken

TokenCipher
KaitenCredentialVerifier
Clock

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

Не менять frozen field inventory.

Не добавлять provider response payload в DTO.

Не добавлять plaintext/ciphertext в public result DTO.

---

# 4. Frozen persistence contract

`kaiten_connections`:

```text
id                        UUID        NOT NULL PK
user_id                   UUID        NOT NULL FK, UNIQUE
api_base_url              TEXT        NOT NULL
kaiten_user_id            TEXT        NULL
workspace_id              TEXT        NULL
encrypted_api_token       BYTEA       NOT NULL
token_encryption_version  SMALLINT    NOT NULL
status                    TEXT        NOT NULL
last_verified_at          TIMESTAMPTZ NULL
created_at                TIMESTAMPTZ NOT NULL
updated_at                TIMESTAMPTZ NOT NULL
```

Allowed status:

```text
ACTIVE
DISABLED
NEEDS_REAUTH
```

One connection per user.

No plaintext token column.

No schema migration.

Alembic remains:

```text
00201_mvp_service_model
```

---

# 5. Frozen repository baseline

`UserRepository` already provides:

```text
get_by_id(user_id)
get_by_id_for_update(user_id)
```

`KaitenConnectionRepository` already provides:

```text
get_for_user(user_id)
get_for_user_for_update(user_id)
create(...)
update_connection(...)
```

Repositories:

```text
receive AsyncSession
do not commit
do not rollback
may flush/refresh
```

`003-04` should preferably require **no new repository abstraction**.

If the actual accepted `update_connection()` signature lacks one of the already-persisted lifecycle fields required here:

```text
kaiten_user_id
workspace_id
token_encryption_version
status
last_verified_at
```

extend that existing method narrowly and explicitly.

Do not add a generic `update(**kwargs)` repository method.

---

# 6. Git checkpoint — mandatory before `003-04`

`003-03` is accepted by the user but remains uncommitted.

Before changing service/verifier code, create a checkpoint.

## 6.1. Inspect current state

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

Expected HEAD before checkpoint:

```text
e577ed9 feat: add identity onboarding service
```

Record actual state rather than forcing expected SHA if repository legitimately changed.

---

# 7. Expected accepted `003-03` inventory

Approximately:

```text
.env.example

src/kvc_config/settings.py

src/kvc_integrations/security/__init__.py
src/kvc_integrations/security/token_cipher.py

tests/unit/test_imports.py
tests/unit/test_token_cipher_adapter.py
tests/unit/test_token_cipher_config.py

codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md
codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
```

The current input prompt:

```text
codex/prompts/003_04_kaiten_connection_service_implementation_prompt.md
```

must remain outside the `003-03` checkpoint.

---

# 8. Pre-checkpoint gate

Before staging accepted `003-03`:

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

Accepted `003-03` reference:

```text
Python 3.12.9
pytest = 154 passed
pytest -W error = 154 passed
ruff PASS
mypy PASS
pip check PASS
Alembic current = 00201_mvp_service_model
Alembic check = no drift
```

If current prompt formatting causes the only Ruff-format failure, minimally format the current prompt without including it in the checkpoint.

---

# 9. Pre-checkpoint secret audit

Inspect `003-03` candidate files.

Confirm no real:

```text
Kaiten token
Fernet key
Authorization value
Bearer value
database password
private user/workspace/card data
```

`.env` must remain ignored and unstaged.

Do not print secret values.

If a real secret exists in checkpoint candidates:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

---

# 10. Stage accepted `003-03` explicitly

Do not use:

```text
git add .
```

Stage only accepted `003-03` files.

Then run:

```powershell
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
git status --short
```

Review staged diff including:

```text
.env.example contains placeholders only
AppSettings key JSON remains secret-aware
no runtime startup wiring was introduced
no real keys
```

---

# 11. Create accepted `003-03` checkpoint

If gate/diff/security pass:

```powershell
git commit -m "feat: add versioned token cipher adapter"
```

Do not amend earlier commits.

Do not push.

Do not merge.

Do not rebase.

After commit:

```powershell
git log --oneline --decorate -6
git status --short
git diff --check
```

Record new checkpoint SHA in report.

---

# 12. `003-04` application package shape

Create:

```text
src/kvc_application/services/kaiten_connection.py
```

Update as needed:

```text
src/kvc_application/services/__init__.py
src/kvc_application/__init__.py
```

Public application service:

```text
KaitenConnectionService
```

Do not create a service framework/base class.

Do not merge IdentityService and KaitenConnectionService.

---

# 13. `KaitenConnectionService` constructor — frozen contract

Implement:

```python
class KaitenConnectionService:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        verifier: KaitenCredentialVerifier,
        token_cipher: TokenCipher,
        clock: Clock,
    ) -> None: ...
```

Dependencies are injected.

The service must not construct:

```text
AsyncEngine
sessionmaker
httpx client
Fernet
AppSettings
provider client
```

inside business methods.

Do not load `.env`.

---

# 14. Public API — exact

Implement the already frozen methods:

```python
async def bind_or_replace_connection(
    self,
    input: BindKaitenConnectionInput,
) -> KaitenConnectionResult: ...


async def disable_connection(
    self,
    user_id: UUID,
) -> KaitenConnectionResult: ...


async def get_active_connection_secret(
    self,
    user_id: UUID,
) -> ActiveKaitenConnectionSecret: ...


async def mark_needs_reauth(
    self,
    input: MarkKaitenNeedsReauthInput,
) -> KaitenConnectionResult | None: ...
```

Do not add public variants such as:

```text
create_connection
replace_connection
enable_connection
reauthenticate
get_token
```

The explicit verified `bind_or_replace_connection` path is also the MVP re-enable path for `DISABLED`/`NEEDS_REAUTH` connection states, provided the KVC user itself is ACTIVE.

---

# 15. User lifecycle contract

KVC user states:

```text
ACTIVE
DISABLED
```

For:

```text
bind_or_replace_connection
get_active_connection_secret
```

require:

```text
user.status == ACTIVE
```

Otherwise:

```text
UserDisabled
```

`disable_connection` remains allowed even when the KVC user is already `DISABLED`, because disabling/re-confirming disabled connection state is safe and idempotent.

`mark_needs_reauth` does not re-enable a user and does not need to reject solely because user status changed; its correctness is guarded by the connection snapshot/status.

---

# 16. Missing user semantics

A `user_id` supplied to application service must already refer to a KVC user created by `IdentityService`.

If the user row is missing:

```text
PersistenceConflict
```

Do not auto-create users here.

Do not introduce:

```text
UserMissing
```

unless a genuine frozen-contract blocker is discovered.

Use safe diagnostic text.

---

# 17. Status validation at persistence boundary

Do not blindly cast ORM strings.

Validate persisted user status:

```text
ACTIVE
DISABLED
```

and connection status:

```text
ACTIVE
DISABLED
NEEDS_REAUTH
```

Unexpected persisted status:

```text
PersistenceConflict
```

Do not return an invalid typed DTO.

---

# 18. Verification endpoint — frozen MVP contract

Implement concrete adapter under:

```text
src/kvc_integrations/kaiten/
```

Preferred file:

```text
src/kvc_integrations/kaiten/credential_verifier.py
```

Concrete class:

```text
KaitenHttpCredentialVerifier
```

Official Kaiten REST verification operation:

```text
GET {api_base_url}/users/current
```

where `api_base_url` is already the API root, for example:

```text
https://<workspace>.kaiten.ru/api/latest
```

The corresponding official route is:

```text
GET /api/latest/users/current
```

Do not use a test card to verify credentials.

Do not mutate Kaiten.

Do not use:

```text
GET arbitrary card
PATCH card
board mutation
workspace mutation
```

for credential verification.

---

# 19. `api_base_url` semantics

`BindKaitenConnectionInput.api_base_url` means:

```text
Kaiten REST API root
```

Examples of accepted semantic shape:

```text
https://example.kaiten.ru/api/latest
https://example.kaiten.ru/api/v1
```

The verifier should safely join:

```text
api_base_url.rstrip("/") + "/users/current"
```

Do not silently append `/api/latest` if the caller already supplies the API root.

Do not normalize a completely different site URL into an assumed API endpoint.

If the endpoint returns provider `404`/unexpected response:

```text
KaitenVerificationFailed
```

The successfully verified `api_base_url` is what gets persisted.

---

# 20. HTTP client dependency

Use existing:

```text
httpx
```

Concrete verifier should receive an injected:

```python
httpx.AsyncClient
```

or an equivalent existing project HTTP-client dependency pattern.

Preferred constructor:

```python
class KaitenHttpCredentialVerifier:
    def __init__(self, client: httpx.AsyncClient) -> None: ...
```

Do not instantiate a new long-lived global client inside each verification call.

Do not store user token in:

```text
client.headers
client.auth
global state
```

Send credential only in the individual request.

Tests should use:

```text
httpx.MockTransport
```

or equivalent deterministic HTTP stub.

---

# 21. Authorization contract

Incoming `plaintext_token` is the raw credential.

Verifier sends:

```text
Authorization: Bearer <plaintext_token>
```

for that request only.

Do not persist the header.

Do not log the header.

Do not include it in exceptions/reports.

Do not place token in URL/query parameters.

Do not mutate shared `AsyncClient.headers` with user credentials.

---

# 22. Verifier success parsing

On HTTP `200`:

1. parse JSON;
2. require top-level object;
3. require stable `id`;
4. normalize `id` to:

```text
str
```

5. return:

```python
KaitenCredentialVerification(
    kaiten_user_id=str(id_value),
    workspace_id=None,
)
```

For this MVP adapter:

```text
workspace_id = None
```

Do not infer workspace ID from hostname/domain.

Do not persist:

```text
email
full_name
username
avatar
notification settings
provider response body
```

The user/account ID is sufficient for credential provenance at this stage.

---

# 23. Verifier HTTP/error mapping

Map:

## Authentication/unusable credential

```text
401
403
```

to:

```text
KaitenAuthenticationFailed
```

Use a generic safe message.

## Temporary availability

Map at minimum:

```text
408
429
5xx
httpx.TimeoutException
httpx.TransportError
```

to:

```text
KaitenTemporarilyUnavailable
```

Do not treat temporary outage as bad credentials.

## Unexpected verification contract

Map:

```text
other unexpected 4xx
404 due wrong endpoint/base
invalid/malformed JSON
non-object JSON
missing/invalid id
unexpected successful response contract
```

to:

```text
KaitenVerificationFailed
```

Do not include raw response body.

---

# 24. Provider error privacy

Provider errors may include only safe metadata such as:

```text
error class
HTTP status code
operation name
```

Do not include:

```text
Authorization header
plaintext token
full response body
cookies
secret-bearing URL/query
private user profile payload
```

Tests must explicitly verify the synthetic token is absent from exception:

```text
str(exc)
repr(exc)
```

---

# 25. No live Kaiten call in `003-04`

This is an implementation stage.

Do not use the user's live `.env` token.

Do not execute a real request against the user's Kaiten workspace.

All verifier acceptance here must be deterministic via mocked HTTP transport.

A separate `003-05` full acceptance stage may decide whether a read-only live verifier probe is useful.

Do not mutate any live card.

---

# 26. Concrete UTC clock adapter

Implement a tiny concrete clock, preferably:

```text
src/kvc_integrations/system/clock.py
```

or another clearly neutral integration/system location.

Class:

```python
class UtcClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
```

It structurally satisfies `Clock`.

Do not call local-time `datetime.now()` without timezone.

Do not add time libraries.

Do not inject system clock directly into service tests; use a deterministic fake clock.

---

# 27. `bind_or_replace_connection` — high-level flow

Frozen successful ordering:

```text
1. Short read/preflight of user.
2. Reject missing user.
3. Reject DISABLED user.
4. Verify plaintext credential through KaitenCredentialVerifier.
5. Encrypt plaintext through TokenCipher.
6. Obtain verified_at from Clock.
7. Open short DB transaction.
8. Lock user row.
9. Re-check user still ACTIVE.
10. Lock existing connection row if present.
11. Create or update connection.
12. Persist:
        api_base_url
        kaiten_user_id
        workspace_id
        encrypted_api_token
        token_encryption_version
        status = ACTIVE
        last_verified_at
13. Commit.
14. Return non-secret KaitenConnectionResult.
```

The HTTP call must occur before row locking.

---

# 28. Bind preflight read

Before verifier network call:

```text
open a short session
read user by id without FOR UPDATE
```

If missing:

```text
PersistenceConflict
```

If:

```text
DISABLED
```

raise:

```text
UserDisabled
```

This avoids unnecessary external credential verification for a disabled/missing account.

Release the session before the HTTP verification.

Do not hold DB transaction/connection while waiting for Kaiten.

---

# 29. Verification failure preserves existing state

If verifier raises:

```text
KaitenAuthenticationFailed
KaitenTemporarilyUnavailable
KaitenVerificationFailed
```

then:

```text
do not encrypt
do not open the write transaction
do not modify current kaiten_connections row
do not change status
do not change token
do not change last_verified_at
```

A previously working ACTIVE connection remains unchanged on transient verification failure.

An invalid replacement must not destroy the old credential.

---

# 30. Encryption failure preserves existing state

If:

```text
TokenCipher.encrypt()
```

raises:

```text
CredentialEncryptionFailed
```

then:

```text
do not open/write persistence transaction
leave existing connection unchanged
```

Do not catch and reclassify it as provider error.

Do not log plaintext.

---

# 31. `Clock.now()` timing

Obtain `verified_at` only after successful credential verification.

It must represent:

```text
successful verifier completion
```

not request reception time.

Use the injected `Clock`.

A deterministic fake clock is required in tests.

The production `UtcClock` returns timezone-aware UTC.

---

# 32. Final write locking order

All connection mutation methods that lock both rows must use canonical order:

```text
1. users row FOR UPDATE
2. kaiten_connections row FOR UPDATE
```

Specifically:

```text
bind_or_replace_connection
disable_connection
```

and `get_active_connection_secret` may follow the same order.

This consistent order reduces deadlock risk.

Do not lock connection first and user second in another method.

---

# 33. Bind/replacement re-check under lock

After external verification/encryption, the state may have changed.

Inside write transaction:

```text
user = get_by_id_for_update(user_id)
```

Re-check:

```text
user exists
user.status == ACTIVE
```

If user became disabled while verification was in flight:

```text
UserDisabled
```

and do not persist new credential.

Then:

```text
connection = get_for_user_for_update(user_id)
```

Create/update from current state.

---

# 34. First bind

If no connection exists after locks:

```text
create one row
status = ACTIVE
```

Persist:

```text
api_base_url
verification.kaiten_user_id
verification.workspace_id
encrypted.ciphertext
encrypted.version
last_verified_at
```

Return:

```text
KaitenConnectionResult
```

One user -> one row.

No additional local Kaiten data.

---

# 35. Explicit replacement/rebind

If an existing connection is:

```text
ACTIVE
NEEDS_REAUTH
DISABLED
```

a successful explicit `bind_or_replace_connection` by an ACTIVE KVC user may replace/re-enable it.

After successful verified write:

```text
status = ACTIVE
```

Update all credential-derived fields:

```text
api_base_url
kaiten_user_id
workspace_id
encrypted_api_token
token_encryption_version
last_verified_at
```

Do not create another connection row.

Connection `id` remains unchanged for replacement.

---

# 36. Concurrent replacements

Two concurrent explicit binds/replacements:

```text
T1 verify A outside locks
T2 verify B outside locks
```

Both may succeed.

Final persistence serializes through:

```text
users FOR UPDATE
then connection FOR UPDATE
```

MVP winner semantics:

```text
last committed verified replacement wins
```

Tests must prove one row remains and the final row corresponds to the later serialized write.

Do not use distributed locks.

Do not hold row locks during HTTP calls.

---

# 37. Same token repeated

Fernet encryption is randomized, so a repeated verified bind of the same logical plaintext may produce different ciphertext.

Frozen idempotency requirement is:

```text
one connection row
ACTIVE
valid current credential
```

It is **not**:

```text
identical ciphertext bytes
identical snapshot
unchanged last_verified_at
```

A repeated explicit verified bind is a new successful credential persistence event and may create a new snapshot even for the same plaintext token.

Document this explicitly.

---

# 38. `KaitenConnectionResult` mapping

Build result only from non-secret fields:

```text
connection_id
user_id
status
api_base_url
kaiten_user_id
workspace_id
last_verified_at
```

Do not include:

```text
encrypted_api_token
token_encryption_version
snapshot
plaintext
```

Validate connection status before mapping.

---

# 39. `disable_connection` semantics

Flow:

```text
1. Open session.begin().
2. Lock user row.
3. Missing user -> PersistenceConflict.
4. Accept ACTIVE or DISABLED KVC user for this safe disable operation.
5. Lock connection row.
6. Missing connection -> KaitenConnectionMissing.
7. If connection.status == DISABLED:
       return current result idempotently.
8. If ACTIVE or NEEDS_REAUTH:
       set status = DISABLED.
9. Do not erase token/ciphertext.
10. Do not change api_base_url.
11. Do not change external IDs.
12. Do not change last_verified_at.
13. Commit.
14. Return non-secret result.
```

Do not delete the connection row.

---

# 40. Repeated disable

Required:

```text
ACTIVE -> DISABLED
repeat -> DISABLED

NEEDS_REAUTH -> DISABLED
repeat -> DISABLED
```

No error for repeated disable when the row exists.

Missing connection remains:

```text
KaitenConnectionMissing
```

---

# 41. `get_active_connection_secret` — purpose

This method is internal application API only.

It exists for a future application command service immediately before a Kaiten call.

It must not be used as:

```text
HTTP response
MAX response
CLI output
log payload
debug dump
```

It returns:

```text
plaintext token
+
exact captured persisted credential snapshot
```

with existing `repr=False` protections.

---

# 42. `get_active_connection_secret` flow

Frozen flow:

```text
1. Open short transaction.
2. Lock user row.
3. Missing user -> PersistenceConflict.
4. DISABLED user -> UserDisabled.
5. Lock connection row.
6. Missing -> KaitenConnectionMissing.
7. Validate connection status.
8. DISABLED -> KaitenConnectionDisabled.
9. NEEDS_REAUTH -> KaitenConnectionNeedsReauth.
10. ACTIVE:
       capture snapshot
       decrypt credential through TokenCipher
       return internal ActiveKaitenConnectionSecret
11. Commit/release locks.
```

Snapshot:

```text
connection_id
encrypted_api_token
token_encryption_version
```

Do not use `updated_at` as the snapshot in this frozen MVP contract.

---

# 43. Snapshot capture — exact contract

Construct:

```python
KaitenCredentialSnapshot(
    connection_id=connection.id,
    encrypted_api_token=bytes(connection.encrypted_api_token),
    token_encryption_version=connection.token_encryption_version,
)
```

or equivalent exact immutable bytes representation.

Snapshot identity is:

```text
connection_id
+
ciphertext bytes
+
crypto key version
```

`token_encryption_version` alone is insufficient.

Do not add hash/fingerprint/revision columns.

---

# 44. Decrypt behavior

Call:

```python
token_cipher.decrypt(
    connection.encrypted_api_token,
    connection.token_encryption_version,
)
```

`CredentialDecryptionFailed` propagates as the application credential error.

Do not:

```text
mark NEEDS_REAUTH automatically
delete connection
disable user
try another key version
```

A local decryption/configuration failure is not equivalent to a Kaiten auth failure.

---

# 45. Lock duration for decrypt

The frozen specification permits decryption while the user/connection snapshot is locked.

Fernet decryption is local and bounded.

Keep the implementation straightforward:

```text
lock
capture
decrypt
return
```

Do not perform provider network IO while holding these locks.

If implementation chooses to copy the snapshot under lock and decrypt immediately after transaction release, prove that the returned snapshot/plaintext pair still refers to the same captured bytes and that frozen behavior is unchanged.

Prefer the simpler frozen algorithm unless there is a concrete reason otherwise.

---

# 46. `mark_needs_reauth` — critical stale-race contract

Input:

```text
user_id
snapshot
reason
```

`reason` is sanitized internal diagnostic metadata only.

There is no persistence column for `reason` in this branch.

Do not store it.

Do not log raw provider response through it.

Do not add schema.

---

# 47. `mark_needs_reauth` exact algorithm

Implement:

```text
1. Open short DB transaction.
2. Lock current kaiten_connections row for input.user_id.
3. If no connection:
       return None.
4. Compare:
       current.id == snapshot.connection_id
       current.encrypted_api_token == snapshot.encrypted_api_token
       current.token_encryption_version == snapshot.token_encryption_version
5. If any differs:
       stale failure -> return None, no mutation.
6. Validate status.
7. If status == DISABLED:
       return current non-secret result, no mutation.
8. If status == NEEDS_REAUTH:
       return current result idempotently.
9. If status == ACTIVE:
       update status = NEEDS_REAUTH.
10. Commit.
11. Return result.
```

No user-row lock is required here because the method never re-enables a user and connection-row serialization is sufficient for this compare-and-mark transition.

Do not later acquire user lock after connection lock.

---

# 48. Stale race — required proof

Deterministic test:

```text
connection stores snapshot A
get_active_connection_secret returns A

explicit replacement writes snapshot B
same connection id may remain
crypto version may remain identical
ciphertext B differs

old in-flight call reports auth failure using A
mark_needs_reauth(A)
```

Expected:

```text
return None
current connection remains ACTIVE
snapshot B remains persisted
```

Critical variation:

```text
A.token_encryption_version == B.token_encryption_version
```

must still be stale due different ciphertext.

This test is mandatory.

---

# 49. Current-snapshot auth failure

When current connection is:

```text
ACTIVE
```

and input snapshot exactly matches:

```text
id
ciphertext
crypto version
```

then:

```text
ACTIVE -> NEEDS_REAUTH
```

Token remains encrypted/persisted.

No deletion.

No plaintext.

No verification network call inside `mark_needs_reauth`.

---

# 50. Repeated/current status behavior

Mandatory:

```text
same current snapshot + ACTIVE
    -> NEEDS_REAUTH

same current snapshot + NEEDS_REAUTH
    -> idempotent NEEDS_REAUTH result

same current snapshot + DISABLED
    -> idempotent DISABLED result, no change

different snapshot + any status
    -> None, no mutation
```

Snapshot mismatch is checked before status transition.

---

# 51. Disable-vs-reauth race

Both mutate/lock the same connection row.

Required outcome:

```text
no invalid status
no resurrection
```

Examples:

```text
disable commits first:
    mark sees DISABLED -> leaves DISABLED

mark commits first:
    connection NEEDS_REAUTH
    disable then sets DISABLED
```

Final allowed outcomes preserve explicit disable dominance once disable commits.

No deadlock cycle should be introduced.

---

# 52. Bind-vs-disable race

Canonical lock order:

```text
user -> connection
```

for both methods.

Because bind verification occurs before locking:

```text
verified bind may be in flight
user/connection can change
```

Final locked re-check determines outcome.

Required:

```text
if KVC user becomes DISABLED before bind write:
    bind -> UserDisabled
    no new credential persisted
```

For connection-only disable while user remains ACTIVE:

```text
a later explicit verified bind may re-enable to ACTIVE
```

which is the accepted explicit rebind semantics.

---

# 53. Bind-vs-mark race

If old command snapshot A is in flight while bind replaces to B:

```text
bind writes B
mark(A) later compares snapshot
    -> stale -> no-op
```

If mark(A) commits first:

```text
A becomes NEEDS_REAUTH
explicit verified bind B later writes ACTIVE
```

Both are correct.

Tests should cover at least deterministic sequentialized versions of both orderings.

---

# 54. `last_verified_at` lifecycle

Set/update only on:

```text
successful verified first bind
successful verified replacement/rebind
```

Do not change on:

```text
disable
mark_needs_reauth
get_active_connection_secret
failed verifier
failed encryption
stale mark
```

Use injected `Clock`.

Tests must use fixed timezone-aware UTC datetimes.

---

# 55. `kaiten_user_id` lifecycle

On every successful bind/replacement:

```text
replace with latest verifier result
```

Concrete verifier returns:

```text
str(current_user.id)
```

Do not preserve an old user ID if successful verifier now reports another account.

The explicit replacement is authoritative.

---

# 56. `workspace_id` lifecycle

Concrete MVP verifier returns:

```text
None
```

Therefore successful bind/replacement through this verifier persists:

```text
workspace_id = None
```

Do not infer from domain.

Do not retain stale previous workspace ID when replacing via a verifier result that explicitly has `None`; repository update should reflect verifier DTO exactly.

This field remains available for a future richer verification contract.

---

# 57. Repository update exactness

Inspect actual `KaitenConnectionRepository`.

A successful replacement must be able to update exactly:

```text
api_base_url
kaiten_user_id
workspace_id
encrypted_api_token
token_encryption_version
status
last_verified_at
```

If current method already supports these fields, use it.

If not, extend its explicit signature minimally.

Repository still must not:

```text
encrypt
decrypt
verify network
commit
rollback
```

Add tests if signature changes.

---

# 58. Persistence error mapping

Map known persistence invariant failures:

```text
PersistenceInvariantError
```

to:

```text
PersistenceConflict
```

where appropriate.

A one-connection-per-user unique race should normally be prevented by locking the parent user row before create.

If an unexpected `IntegrityError` still occurs in final persistence:

```text
rollback transaction
map to PersistenceConflict
```

Do not retry external verifier automatically.

Do not re-run encryption/HTTP call in a DB retry loop.

No infinite retry.

---

# 59. First-bind concurrency strategy

Two first binds for same ACTIVE user:

```text
verify/encrypt independently outside lock
```

Then:

```text
T1 locks user
T2 waits
T1 creates connection, commits
T2 locks user
T2 sees existing connection under lock
T2 updates same row
```

Result:

```text
one connection row
last committed verified credential wins
```

This uses:

```text
users row as serialization parent
```

and existing:

```text
UNIQUE(kaiten_connections.user_id)
```

as final DB guard.

No distributed lock.

---

# 60. HTTP verifier unit tests

Add e.g.:

```text
tests/unit/test_kaiten_credential_verifier.py
```

Use `httpx.MockTransport`.

Cover at minimum:

```text
200 object with numeric id -> kaiten_user_id string
workspace_id is None
request path ends /users/current
Authorization sent as Bearer raw token
token not placed in URL
shared client headers are not permanently mutated

401 -> KaitenAuthenticationFailed
403 -> KaitenAuthenticationFailed

408 -> KaitenTemporarilyUnavailable
429 -> KaitenTemporarilyUnavailable
500 -> KaitenTemporarilyUnavailable
503 -> KaitenTemporarilyUnavailable
TimeoutException -> KaitenTemporarilyUnavailable
TransportError -> KaitenTemporarilyUnavailable

404 -> KaitenVerificationFailed
unexpected 4xx -> KaitenVerificationFailed
malformed JSON -> KaitenVerificationFailed
JSON list/scalar -> KaitenVerificationFailed
missing id -> KaitenVerificationFailed
invalid id shape -> KaitenVerificationFailed

plaintext token absent from error strings
raw response body absent from error strings
```

Do not make any live request.

---

# 61. Verifier request capture security test

Use synthetic token marker:

```text
SYNTHETIC-KAITEN-TOKEN-MUST-NOT-LEAK
```

It is acceptable for the test transport to inspect the outgoing request header in-memory to prove correct behavior.

Do not:

```text
print it
snapshot it
write it to report
```

Assertions should only prove:

```text
Authorization header was correctly formed
marker absent from exceptions/repr/loggable outputs
```

---

# 62. Clock tests

Add focused test for:

```text
UtcClock.now()
```

Assert:

```text
tzinfo is present
UTC offset == zero
```

Do not assert exact wall-clock value.

Service unit tests use fake deterministic clock instead.

---

# 63. `KaitenConnectionService` unit tests

Add e.g.:

```text
tests/unit/test_kaiten_connection_service.py
```

Use deterministic fake:

```text
verifier
token cipher
clock
session/repository seams as appropriate
```

Cover at minimum:

## Bind

```text
missing user -> PersistenceConflict before verifier
disabled user -> UserDisabled before verifier
valid first bind -> ACTIVE result
invalid credential -> old state untouched
temporary verifier outage -> old state untouched
verification contract failure -> old state untouched
encryption failure -> old state untouched
user disabled during external verification -> UserDisabled on locked re-check
```

## Disable

```text
missing connection -> KaitenConnectionMissing
ACTIVE -> DISABLED
NEEDS_REAUTH -> DISABLED
DISABLED -> idempotent DISABLED
disabled KVC user may still disable connection
```

## Get secret

```text
disabled KVC user -> UserDisabled
missing connection -> KaitenConnectionMissing
DISABLED connection -> KaitenConnectionDisabled
NEEDS_REAUTH -> KaitenConnectionNeedsReauth
ACTIVE -> decrypt + snapshot
decrypt failure propagates CredentialDecryptionFailed
```

## Mark reauth

```text
missing -> None
matching ACTIVE -> NEEDS_REAUTH
matching NEEDS_REAUTH -> idempotent
matching DISABLED -> unchanged
stale snapshot -> None
same crypto version but different ciphertext -> stale None
```

---

# 64. Real PostgreSQL integration tests

Add:

```text
tests/integration/test_kaiten_connection_service_postgresql.py
```

Use configured development PostgreSQL safety convention.

No live Kaiten calls.

Verifier is a deterministic fake.

TokenCipher may use actual:

```text
VersionedFernetTokenCipher
```

with ephemeral test key generated at runtime.

Clock is deterministic fake UTC.

---

# 65. PostgreSQL safety prerequisites

Before mutating integration DB confirm:

```text
KVC_APP_ENV == development
current_database() == kvc_dev
alembic_version == 00201_mvp_service_model
```

Record baseline counts.

Use synthetic users/connections only.

Never use a real token.

Never read live `.env` Kaiten token for tests.

Cleanup/rollback must return business tables to original baseline.

Do not delete unrelated user-created development rows.

---

# 66. Integration test — first bind

Create synthetic ACTIVE KVC user.

Call service with:

```text
synthetic api_base_url
synthetic plaintext token
fake verifier success
real test TokenCipher
fixed UTC clock
```

Prove:

```text
one kaiten_connections row
status ACTIVE
api_base_url correct
kaiten_user_id from verifier
workspace_id None
encrypted_api_token != plaintext bytes
token_encryption_version == active crypto version
last_verified_at == fixed clock
service result contains no token/ciphertext
```

Decrypt persisted ciphertext through test cipher and prove it round-trips synthetic token.

Do not print ciphertext or plaintext.

---

# 67. Integration test — replacement

Start with connection A.

Explicit bind B.

Prove:

```text
same connection.id
same user_id
one row only
status ACTIVE
api_base_url updated
kaiten_user_id updated
workspace_id reflects verifier
ciphertext changed
plaintext decrypts to B
last_verified_at updated
```

Old persisted snapshot differs.

---

# 68. Integration test — re-enable

Starting statuses:

```text
NEEDS_REAUTH
DISABLED
```

Successful explicit verified bind:

```text
-> ACTIVE
```

Prove token/base/user metadata replaced.

KVC user itself must remain ACTIVE.

For a DISABLED KVC user:

```text
bind rejected UserDisabled
connection remains unchanged
```

---

# 69. Integration test — verification failure preserves old row

Existing ACTIVE connection.

Fake verifier raises:

```text
KaitenAuthenticationFailed
```

and separately:

```text
KaitenTemporarilyUnavailable
```

After call:

```text
same status
same ciphertext
same token_encryption_version
same last_verified_at
same api_base_url
same external IDs
```

No write should have occurred.

---

# 70. Integration test — encryption failure preserves old row

Use test TokenCipher that raises:

```text
CredentialEncryptionFailed
```

after verifier success.

Prove existing row unchanged exactly.

No partial update.

---

# 71. Integration test — get secret snapshot

For ACTIVE row:

```text
get_active_connection_secret
```

returns synthetic plaintext and snapshot.

Prove snapshot equals persisted:

```text
id
ciphertext
version
```

Then confirm `repr()` of returned object contains neither:

```text
plaintext marker
ciphertext marker
```

Use existing DTO security protections.

---

# 72. Integration test — stale auth failure after replacement

Mandatory high-value test:

```text
1. bind token A using crypto version 1
2. get_active_connection_secret -> snapshot A
3. bind token B using the SAME crypto active version 1
4. connection id remains same
5. snapshot B ciphertext differs from A
6. mark_needs_reauth(snapshot A)
```

Expected:

```text
returns None
connection remains ACTIVE
persisted token decrypts to B
```

This proves:

```text
token_encryption_version is not credential revision
```

---

# 73. Integration test — current auth failure

After obtaining current snapshot:

```text
mark_needs_reauth(current snapshot)
```

Expected:

```text
status NEEDS_REAUTH
token remains persisted unchanged
last_verified_at unchanged
```

Repeat:

```text
same result
no further mutation required
```

---

# 74. Integration test — disabled mark

Connection DISABLED, matching snapshot.

Call:

```text
mark_needs_reauth
```

Expected:

```text
DISABLED
```

No reactivation.

No transition to NEEDS_REAUTH.

---

# 75. Integration test — disable lifecycle

Test:

```text
ACTIVE -> DISABLED
repeat -> DISABLED
```

and:

```text
NEEDS_REAUTH -> DISABLED
```

Assert token bytes remain unchanged and still encrypted in DB.

Do not erase secrets on disable.

---

# 76. Integration test — first-bind concurrency

If current test infrastructure supports deterministic two-session concurrency cleanly, add a real PostgreSQL test.

Use coordination primitives:

```text
asyncio.Event
barrier-like events
```

not `sleep()`.

Goal:

```text
two successful explicit binds for same user
one connection row
final value from later serialized transaction
```

If a fully deterministic service-level concurrent test would require invasive production hooks, prove instead:

1. unit-level orchestration/locking order;
2. repository `FOR UPDATE` behavior;
3. PostgreSQL unique constraint;
4. deterministic sequential simulation of post-verification interleaving.

Reserve stress timing test for `003-05`.

Do not add flaky sleeps.

---

# 77. Integration test — user disabled in-flight

Deterministic service unit or multi-session integration scenario:

```text
1. preflight sees ACTIVE
2. verifier is held by test event
3. another transaction sets user DISABLED
4. verifier completes
5. bind enters final transaction
```

Expected:

```text
UserDisabled
no credential replacement
```

This proves locked status re-check.

If implementing this as live PostgreSQL concurrency becomes flaky, use deterministic unit orchestration seam plus DB integration for locked status behavior separately.

---

# 78. Repository locking tests

Confirm existing:

```text
UserRepository.get_by_id_for_update
KaitenConnectionRepository.get_for_user_for_update
```

compile/use:

```text
FOR UPDATE
```

If `update_connection` was extended, add exact tests proving it updates only allowed connection fields and still does not commit/rollback.

Do not add a new lock repository if current methods suffice.

---

# 79. No provider call under DB row lock

Add an orchestration test proving:

```text
verifier completes before get_by_id_for_update/write transaction
```

This may use ordered events/spies.

Critical invariant:

```text
no network wait while user/connection row lock is held
```

Do not rely only on source review.

---

# 80. No automatic verification during `get_active_connection_secret`

That method:

```text
decrypts locally
```

but does not call verifier.

Do not turn every command into a preflight `/users/current` call.

Future real Kaiten command failure will drive:

```text
mark_needs_reauth
```

when appropriate.

This avoids redundant provider calls.

---

# 81. No automatic `NEEDS_REAUTH` on verifier replacement failure

During explicit replacement:

```text
new token invalid
```

must not alter existing status.

Example:

```text
existing ACTIVE token A
user enters invalid token B
verifier rejects B
```

Result:

```text
A remains ACTIVE
```

Do not mark A as `NEEDS_REAUTH`.

---

# 82. Provider adapter scope

`KaitenHttpCredentialVerifier` is the only provider HTTP behavior required here.

Do not implement:

```text
list cards
get card
move card
comment
deadline
attachments
summary
boards/spaces query
```

These belong to future command/query integration branches.

Do not create a generic all-purpose Kaiten client in `003-04`.

---

# 83. No local Kaiten content cache

Do not persist current-user response beyond:

```text
kaiten_user_id
workspace_id
```

No provider profile table.

No card/board table.

No JSONB current-user snapshot.

Kaiten remains source of truth.

---

# 84. No live credential persistence in tests

Never use:

```text
KVC_KAITEN_API_TOKEN
```

from `.env`.

Tests create synthetic token strings.

Even though DB stores encrypted values, real credentials are forbidden in test fixtures.

---

# 85. Error taxonomy — exact use

Use existing classes only.

## User/state

```text
UserDisabled
KaitenConnectionMissing
KaitenConnectionDisabled
KaitenConnectionNeedsReauth
PersistenceConflict
```

## Provider

```text
KaitenAuthenticationFailed
KaitenTemporarilyUnavailable
KaitenVerificationFailed
```

## Crypto

```text
CredentialEncryptionFailed
CredentialDecryptionFailed
```

Do not add:

```text
KaitenForbidden
KaitenRateLimited
ConnectionConflict
ClockError
HttpError
```

unless a truly blocking frozen gap exists.

---

# 86. Safe `reason` semantics

`MarkKaitenNeedsReauthInput.reason` remains:

```text
str
```

Treat it only as an internal sanitized reason code/text supplied by the future calling application workflow.

`003-04` must not persist or log it by default.

Tests may use:

```text
"authentication_failed"
```

Do not feed raw:

```text
HTTP body
exception repr
Authorization data
token
```

into it.

---

# 87. Security/repr audit

Re-confirm existing DTO protections:

```text
BindKaitenConnectionInput.plaintext_token repr=False
ActiveKaitenConnectionSecret.plaintext_token repr=False
ActiveKaitenConnectionSecret.snapshot repr=False
KaitenCredentialSnapshot.encrypted_api_token repr=False
EncryptedToken.ciphertext repr=False
MarkKaitenNeedsReauthInput.snapshot repr=False
MarkKaitenNeedsReauthInput.reason repr=False
```

No new service/adapter repr should expose injected cipher keys, tokens, headers or ciphertext.

---

# 88. Logging policy

Do not add secret-bearing logging.

If logging is introduced, allowed metadata only:

```text
operation
user_id
connection_id
status transition
HTTP status class/code
application error type
```

Forbidden:

```text
plaintext token
ciphertext
Authorization header
Fernet key
raw response body
raw settings key JSON
```

Logging is not required to complete `003-04`.

---

# 89. Composition boundary

Do not modify FastAPI/worker startup to automatically build the service yet unless the repository already has a dedicated composition module explicitly intended for application service construction.

At minimum, production pieces must be independently constructible:

```text
VersionedFernetTokenCipher
KaitenHttpCredentialVerifier
UtcClock
KaitenConnectionService
```

Full transport composition belongs to the subsequent integration/transport branch.

`003-05` will accept the application layer itself.

---

# 90. Config usage

Do not add new config fields for verifier.

`api_base_url` and token are per-user binding input/persisted connection data.

Global development:

```text
KVC_KAITEN_API_BASE_URL
KVC_KAITEN_API_TOKEN
```

used in earlier live probes are not the production per-user connection source for `KaitenConnectionService`.

Do not make service read those global live-test settings.

Crypto settings from `003-03` remain the only configuration required to build the concrete `TokenCipher`.

---

# 91. Unit test fakes — security

Fake verifier should never retain secret input in a public attribute/repr unless the test specifically inspects a transient call record and clears it.

Prefer:

```text
call count
safe api_base_url
event signals
```

If test must prove exact token passed, use a synthetic marker and never print it.

Do not place token markers in test failure messages via broad object equality where avoidable.

---

# 92. Type safety

All new source must pass:

```text
mypy src
```

Avoid broad:

```text
Any
cast(...)
# type: ignore
```

Provider JSON parsing may begin as:

```text
object
```

and narrow explicitly.

Do not type provider payload as application DTO before validation.

---

# 93. HTTP response ID parsing

Accept provider current-user `id` only if it is a stable scalar identifier:

```text
int (not bool)
or
non-empty str
```

Normalize to:

```text
str
```

Reject:

```text
None
bool
list
dict
empty string
```

as:

```text
KaitenVerificationFailed
```

Do not accept arbitrary JSON object coercion.

---

# 94. URL safety

Do not include plaintext token in URL.

Do not include token in query parameters.

For diagnostic errors, avoid echoing full `api_base_url` if it might contain unexpected query/credentials.

The adapter may validate that the computed request URL does not contain:

```text
username/password userinfo
query token from its own construction
```

but do not build a large URL validation framework.

Transport/input validation can become stricter later.

---

# 95. HTTP timeout ownership

Injected `httpx.AsyncClient` owns its timeout configuration.

The verifier should not override a well-configured shared client unless an existing project convention requires a request timeout.

Do not add a second settings surface for timeout in this stage.

Tests simulate timeout exceptions deterministically.

---

# 96. Targeted test gate

After implementation run targeted tests, for example:

```powershell
.venv\Scripts\python.exe -m pytest `
  tests/unit/test_kaiten_credential_verifier.py `
  tests/unit/test_kaiten_connection_service.py `
  tests/unit/test_token_cipher_adapter.py `
  tests/integration/test_kaiten_connection_service_postgresql.py `
  -v
```

plus repository/import tests if touched.

Report:

```text
collected
passed
skipped
warnings
```

---

# 97. Full quality gate

After targeted tests:

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
test count > 154
pytest PASS
pytest -W error PASS
Ruff PASS
mypy PASS
pip check PASS
Alembic current = 00201_mvp_service_model
Alembic check = no drift
```

---

# 98. PostgreSQL final-state verification

Record before integration tests:

```text
current_database
alembic_version
business-table row counts
```

After tests verify counts return exactly to baseline.

Do not assume zero if user has added legitimate development rows.

Use transaction isolation/targeted cleanup for synthetic test data only.

No migration.

No broad truncate.

---

# 99. Secret audit — mandatory

Before report inspect:

```text
new application service
new Kaiten verifier
new clock
repository diff if any
tests
prompt
report
.env.example
Git diff
```

Check for real:

```text
Kaiten token
Authorization value
Fernet key
database password
private user data
card/workspace data
```

Environment variable names are allowed.

Synthetic test markers are allowed.

Never print found secrets.

If real secret found:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

---

# 100. Expected production diff

After `003-03` checkpoint expected approximately:

```text
src/kvc_application/services/kaiten_connection.py
src/kvc_application/services/__init__.py
src/kvc_application/__init__.py

src/kvc_integrations/kaiten/credential_verifier.py
src/kvc_integrations/kaiten/__init__.py

src/kvc_integrations/system/clock.py
src/kvc_integrations/system/__init__.py
```

Possible narrow persistence change:

```text
src/kvc_persistence/repositories/kaiten_connections.py
```

only if existing `update_connection` cannot update frozen fields.

Tests:

```text
tests/unit/test_kaiten_credential_verifier.py
tests/unit/test_kaiten_connection_service.py
tests/unit/test_clock.py
tests/integration/test_kaiten_connection_service_postgresql.py
possibly repository/import tests
```

Prompt/report:

```text
codex/prompts/003_04_kaiten_connection_service_implementation_prompt.md
codex/reports/003_04_kaiten_connection_service_implementation_report.md
```

---

# 101. Unexpected files

Normally no changes to:

```text
Alembic revisions
models.py
pyproject.toml
.env
IdentityService logic
MAX integration
GigaChat integration
STT
notifications
worker
FastAPI transport
```

If they change, explain exact necessity.

Unrelated modifications should not be introduced.

---

# 102. Git discipline after checkpoint

The initial accepted `003-03` checkpoint commit is authorized and required.

After it:

```text
do not commit 003-04 implementation automatically
```

Leave `003-04` code/tests/report in worktree for user acceptance.

Do not:

```text
push
merge
rebase
amend checkpoint
reset --hard
clean -fd
```

---

# 103. No `003-05` work inside this prompt

Do not perform final branch acceptance/closeout.

Do not commit `003-04`.

Do not conduct a live user-token verifier probe.

Do not merge branch.

`003-05` will be a separate full automated/application-service acceptance stage.

---

# 104. Implementation report

Create:

```text
codex/reports/003_04_kaiten_connection_service_implementation_report.md
```

Report must contain at minimum:

1. Executive summary.
2. Frozen sources and precedence.
3. Initial Git/worktree state.
4. Pre-checkpoint `003-03` quality gate.
5. `003-03` secret/diff audit.
6. Exact staged `003-03` inventory.
7. `003-03` checkpoint SHA/message.
8. Post-checkpoint worktree state.
9. `003-04` baseline gate.
10. Final package layout.
11. Concrete verifier implementation.
12. Official verification endpoint used.
13. HTTP client injection strategy.
14. Authorization/header security.
15. Provider success parsing.
16. Provider error mapping.
17. Confirmation no live Kaiten call.
18. Concrete UTC clock.
19. `KaitenConnectionService` constructor/API.
20. User preflight/read semantics.
21. Verification-before-persist ordering.
22. Encryption-before-write ordering.
23. Final locked write/re-check.
24. First-bind behavior.
25. Replacement/re-enable behavior.
26. Concurrent replacement semantics.
27. Repeated same-token semantics.
28. `disable_connection`.
29. `get_active_connection_secret`.
30. Exact credential snapshot.
31. `mark_needs_reauth`.
32. Stale-snapshot race proof.
33. Same crypto-version/different-ciphertext proof.
34. Disable/mark race behavior.
35. Bind/user-disable in-flight proof.
36. `last_verified_at` lifecycle.
37. External IDs lifecycle.
38. Repository changes, if any.
39. Unit tests.
40. Provider adapter tests.
41. PostgreSQL integration tests.
42. Locking/concurrency tests.
43. Failure atomicity/state-preservation tests.
44. Secret/repr/error-redaction tests.
45. PostgreSQL baseline restoration.
46. No schema/dependency changes.
47. Alembic current/check.
48. Targeted gate.
49. Full quality gate.
50. Changed-file classification.
51. Explicit deferred work.
52. Final Git status/diff.
53. Final status.

---

# 105. Changed-file classification

Use:

```text
Application production code:
Integration production code:
Persistence repositories:
Configuration:
Tests:
Alembic/schema:
Dependencies:
Environment/example:
Prompts:
Reports:
Database final state:
Other:
```

Expected:

```text
Configuration:
none

Alembic/schema:
none

Dependencies:
none

Environment/example:
none
```

unless a concrete narrow reason exists.

---

# 106. Explicit deferred work after `003-04`

Still deferred:

```text
003-05:
    full application-service acceptance
    integrated audit of 003-01..003-04
    optional decision on safe read-only live Kaiten verifier probe
    broader concurrency acceptance

003-06:
    branch acceptance
    explicit staging/commit
    Git closeout/integration
```

Future feature branches:

```text
MAX transport/bot
Kaiten card/board query and mutation ports/adapters
voice/STT
GigaChat intent/resolver
dialog context
pending command workflow
attachments/photos
card summary
notification worker/delivery
```

Do not implement them here.

---

# 107. Acceptance criteria — checkpoint

`003-04` cannot begin until:

- branch is `003-application-service-user-onboarding`;
- accepted `003-03` gate is green;
- accepted `003-03` secret audit is clean;
- accepted `003-03` is explicitly staged;
- current `003-04` prompt is excluded;
- checkpoint commit exists:
  - recommended `feat: add versioned token cipher adapter`;
- post-checkpoint worktree contains no unexplained accepted-stage residue.

---

# 108. Acceptance criteria — verifier

Required:

- `KaitenHttpCredentialVerifier` exists;
- uses injected `httpx.AsyncClient`;
- performs only `GET {api_base_url}/users/current`;
- sends request-scoped Bearer auth;
- does not mutate shared client auth headers;
- parses `id` to string;
- returns `workspace_id=None`;
- 401/403 -> `KaitenAuthenticationFailed`;
- 408/429/5xx/timeouts/transport -> `KaitenTemporarilyUnavailable`;
- malformed/unexpected contract -> `KaitenVerificationFailed`;
- token/raw provider body absent from exceptions;
- no live provider call in tests/stage.

---

# 109. Acceptance criteria — service bind/rebind

Required:

- `KaitenConnectionService` exists;
- constructor matches frozen DI contract;
- missing user -> `PersistenceConflict`;
- disabled user rejected before verifier;
- verifier runs outside locked transaction;
- verifier failure leaves old connection exactly unchanged;
- encryption failure leaves old connection exactly unchanged;
- final transaction locks user then connection;
- user status re-checked under lock;
- first bind creates one ACTIVE row;
- replacement retains connection ID;
- replacement updates all credential-derived fields;
- NEEDS_REAUTH -> successful rebind -> ACTIVE;
- DISABLED connection -> explicit successful rebind -> ACTIVE when KVC user ACTIVE;
- KVC user DISABLED cannot rebind;
- `last_verified_at` set only after success;
- public result has no secrets.

---

# 110. Acceptance criteria — disable

Required:

- missing connection -> `KaitenConnectionMissing`;
- ACTIVE -> DISABLED;
- NEEDS_REAUTH -> DISABLED;
- repeated DISABLED -> idempotent;
- disabled KVC user can still safely disable connection;
- token/ciphertext retained;
- last_verified_at retained;
- no deletion.

---

# 111. Acceptance criteria — active secret

Required:

- missing user -> `PersistenceConflict`;
- disabled user -> `UserDisabled`;
- missing connection -> `KaitenConnectionMissing`;
- DISABLED -> `KaitenConnectionDisabled`;
- NEEDS_REAUTH -> `KaitenConnectionNeedsReauth`;
- ACTIVE decrypts successfully;
- snapshot exactly:
  - connection_id;
  - encrypted_api_token;
  - token_encryption_version;
- plaintext/snapshot hidden from repr;
- no verifier network call;
- decrypt failure remains `CredentialDecryptionFailed`.

---

# 112. Acceptance criteria — stale-safe reauth

Required:

- missing connection -> `None`;
- stale snapshot -> `None`;
- stale snapshot does not change status;
- different ciphertext with same crypto version is stale;
- matching ACTIVE -> NEEDS_REAUTH;
- matching NEEDS_REAUTH -> idempotent;
- matching DISABLED -> unchanged DISABLED;
- no reason persistence;
- no schema change;
- no logical credential revision added.

---

# 113. Acceptance criteria — concurrency/transactions

Required:

- canonical user->connection lock ordering;
- no provider HTTP call while row lock held;
- user status re-check after external verifier;
- two verified replacements leave one connection;
- last committed verified write wins;
- bind after connection-only disable may explicitly re-enable;
- bind cannot re-enable DISABLED KVC user;
- stale old auth failure cannot downgrade a freshly replaced credential;
- no distributed locks;
- no automatic provider retry loop;
- no network call inside DB retry loop.

---

# 114. Acceptance criteria — security

Required:

- plaintext never persisted;
- ciphertext only persisted in accepted BYTEA field;
- crypto version persisted as SMALLINT version;
- token absent from logs/errors/reports;
- Authorization absent from logs/errors/reports;
- raw current-user response not persisted;
- no real Kaiten token in tests;
- no real Fernet key in source/report;
- `.env` untouched/ignored;
- public DTOs non-secret;
- internal secret DTO repr-safe.

---

# 115. Acceptance criteria — infrastructure gate

Required:

- no model/schema changes;
- no Alembic revision;
- no new dependency;
- no local Kaiten content tables/cache;
- PostgreSQL baseline restored after tests;
- `pytest` PASS;
- `pytest -W error` PASS;
- Ruff PASS;
- mypy PASS;
- pip check PASS;
- `alembic current = 00201_mvp_service_model`;
- `alembic check = no new upgrade operations`;
- `git diff --check` PASS;
- report created.

---

# 116. Final status

If all implementation criteria pass:

```text
IMPLEMENTED - READY FOR 003-05 FULL APPLICATION SERVICE ACCEPTANCE
```

If verifier/service frozen semantics cannot be implemented without schema/contract redesign:

```text
BLOCKED - FROZEN CONTRACT CONFLICT
```

If accepted `003-03` cannot be safely checkpointed:

```text
BLOCKED - CHECKPOINT WORKTREE CONFLICT
```

If a real secret is discovered:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

Do not start `003-05` inside this prompt.

---

## Главное правило этапа

`003-04` завершает application-service boundary:

```text
MAX identity already resolved
        +
explicit user Kaiten credential
        ↓
verify outside locks
        ↓
encrypt
        ↓
lock/re-check
        ↓
persist one ACTIVE encrypted connection
```

и обеспечивает безопасный дальнейший lifecycle:

```text
ACTIVE
↔ explicit verified replacement
↓
NEEDS_REAUTH
↓
explicit verified rebind -> ACTIVE

ACTIVE / NEEDS_REAUTH
↓
explicit disable
DISABLED
↓
explicit verified rebind -> ACTIVE
```

При этом stale auth failure никогда не имеет права испортить более новый credential snapshot:

```text
snapshot A failure
+
current snapshot B
=
no-op
```

Без MAX transport, card commands, LLM/STT, notification delivery, local Kaiten cache или schema changes.
