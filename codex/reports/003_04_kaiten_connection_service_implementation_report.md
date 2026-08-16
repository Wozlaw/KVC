# 003-04 - KaitenConnectionService implementation report

## 1. Executive summary

Implemented the final application-service workflow for branch `003`:

```text
explicit Kaiten credential input
-> verifier outside locks
-> TokenCipher encryption
-> short locked PostgreSQL transaction
-> one ACTIVE encrypted kaiten_connections row
```

Implemented:

```text
KaitenConnectionService
KaitenHttpCredentialVerifier
UtcClock
first bind
explicit replacement/re-enable
disable
active secret retrieval
stale-safe mark_needs_reauth
unit and PostgreSQL integration tests
```

No MAX transport, Kaiten card command adapter, dialog resolver, notification worker, GigaChat/STT, startup wiring, schema migration, dependency change, or live Kaiten call was added.

Final status:

```text
IMPLEMENTED - READY FOR 003-05 FULL APPLICATION SERVICE ACCEPTANCE
```

## 2. Frozen sources and precedence

Sources used:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
codex/reports/002_03_repository_query_contracts_implementation_report.md
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
codex/prompts/003_04_kaiten_connection_service_implementation_prompt.md
```

Precedence:

```text
003-00a final frozen specification
003-01 frozen application contracts
003-03 accepted crypto contract
003-02 accepted identity implementation
002 accepted persistence/repository contracts
003-04 implementation prompt
```

No frozen contract conflict was found.

## 3. Initial Git/worktree state

Initial branch:

```text
003-application-service-user-onboarding
```

Initial HEAD:

```text
e577ed9 feat: add identity onboarding service
```

Initial status:

```text
 M .env.example
 M src/kvc_config/settings.py
 M tests/unit/test_imports.py
?? codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md
?? codex/prompts/003_04_kaiten_connection_service_implementation_prompt.md
?? codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
?? src/kvc_integrations/security/
?? tests/unit/test_token_cipher_adapter.py
?? tests/unit/test_token_cipher_config.py
```

Ignored local artifacts included `.env`, virtualenv/cache directories, coverage, and `__pycache__` directories.

## 4. Pre-checkpoint `003-03` quality gate

Before staging accepted `003-03`:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
154 passed in 6.48s

.venv\Scripts\python.exe -m pytest -W error
154 passed in 6.30s

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 40 source files

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.

git diff --check
<no output, exit code 0>
```

`ruff format --check .` initially failed only on Python snippets inside the current untracked `003-04` prompt. That prompt was formatted and left outside the `003-03` checkpoint. Final pre-checkpoint format result:

```text
.venv\Scripts\python.exe -m ruff format --check .
98 files already formatted
```

## 5. `003-03` secret/diff audit

Checked `003-03` candidate files without printing matched secret-like lines.

Findings:

```text
No real Kaiten token.
No real Fernet key.
No Authorization or Bearer value.
No real database password.
No private user/workspace/card data.
```

Matches were limited to environment names, `SecretStr`, normative prompt/report text, and synthetic runtime test markers.

## 6. Exact staged `003-03` inventory

Staged explicitly, without `git add .`:

```text
M .env.example
A codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md
A codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
M src/kvc_config/settings.py
A src/kvc_integrations/security/__init__.py
A src/kvc_integrations/security/token_cipher.py
M tests/unit/test_imports.py
A tests/unit/test_token_cipher_adapter.py
A tests/unit/test_token_cipher_config.py
```

Checks:

```text
git diff --cached --check
<no output, exit code 0>

git diff --cached --stat
9 files changed, 3591 insertions(+), 3 deletions(-)
```

The current `003-04` prompt was not staged.

## 7. `003-03` checkpoint SHA/message

Created checkpoint commit:

```text
6294a07 feat: add versioned token cipher adapter
```

Post-checkpoint log:

```text
6294a07 (HEAD -> 003-application-service-user-onboarding) feat: add versioned token cipher adapter
e577ed9 feat: add identity onboarding service
f99b2c8 feat: add application service contracts
568a0bb (002-mvp-service-data-model) docs: close MVP service data model branch
4abdb91 feat: add persistence repository contracts
9cd4f91 feat: add MVP service persistence model
```

## 8. Post-checkpoint worktree state

After checkpoint:

```text
?? codex/prompts/003_04_kaiten_connection_service_implementation_prompt.md
```

`git diff --check` had no output.

## 9. `003-04` baseline gate

Before `003-04` source changes:

```text
.venv\Scripts\python.exe -m pytest
154 passed in 6.09s

.venv\Scripts\python.exe -m pytest -W error
154 passed in 6.41s

.venv\Scripts\python.exe -m ruff format --check .
98 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 40 source files

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

## 10. Final package layout

Application service:

```text
src/kvc_application/services/kaiten_connection.py
src/kvc_application/services/__init__.py
src/kvc_application/__init__.py
```

Integration adapters:

```text
src/kvc_integrations/kaiten/credential_verifier.py
src/kvc_integrations/kaiten/__init__.py
src/kvc_integrations/system/clock.py
src/kvc_integrations/system/__init__.py
```

## 11. Concrete verifier implementation

Implemented:

```text
KaitenHttpCredentialVerifier
```

It structurally satisfies the existing `KaitenCredentialVerifier` protocol and uses an injected `httpx.AsyncClient`.

## 12. Official verification endpoint used

The verifier performs only:

```text
GET {api_base_url.rstrip("/")}/users/current
```

This corresponds to the official route:

```text
GET /api/latest/users/current
```

No test card, card mutation, board mutation, workspace mutation, or generic Kaiten client was implemented.

## 13. HTTP client injection strategy

`KaitenHttpCredentialVerifier` constructor:

```text
__init__(client: httpx.AsyncClient)
```

The adapter does not create a global client and does not own timeout settings. Tests use `httpx.MockTransport`.

## 14. Authorization/header security

The verifier sends:

```text
Authorization: Bearer <plaintext_token>
```

only in the per-request `headers` argument. It does not mutate `AsyncClient.headers`, does not place the token in URL/query parameters, and does not log or persist the header.

Tests prove request-scoped header behavior and that the synthetic token marker is absent from exception strings/reprs.

## 15. Provider success parsing

On HTTP 200:

```text
parse JSON
require top-level object
require id as int (not bool) or non-empty str
return KaitenCredentialVerification(kaiten_user_id=str(id), workspace_id=None)
```

The adapter does not persist or expose email, username, avatar, full provider profile, response body, or workspace inferred from hostname.

## 16. Provider error mapping

Implemented mapping:

```text
401/403 -> KaitenAuthenticationFailed
408/429/5xx -> KaitenTemporarilyUnavailable
httpx.TimeoutException/httpx.TransportError -> KaitenTemporarilyUnavailable
other 4xx/404 -> KaitenVerificationFailed
malformed JSON/non-object/missing or invalid id -> KaitenVerificationFailed
```

Messages are generic and do not include token, Authorization header, full URL, or raw response body.

## 17. Confirmation no live Kaiten call

No live Kaiten request was executed. All verifier tests use deterministic `httpx.MockTransport`.

The user `.env` token was not read for verifier acceptance.

## 18. Concrete UTC clock

Implemented:

```text
src/kvc_integrations/system/clock.py
UtcClock.now() -> datetime.now(UTC)
```

Unit test verifies timezone-aware UTC output without asserting a wall-clock instant.

## 19. `KaitenConnectionService` constructor/API

Implemented:

```text
KaitenConnectionService(sessionmaker, verifier, token_cipher, clock)
bind_or_replace_connection(input)
disable_connection(user_id)
get_active_connection_secret(user_id)
mark_needs_reauth(input)
```

Dependencies are injected. The service does not construct an engine, sessionmaker, HTTP client, Fernet cipher, settings object, or provider client inside business methods.

## 20. User preflight/read semantics

`bind_or_replace_connection` first opens a short read session and reads the user without `FOR UPDATE`.

Behavior:

```text
missing user -> PersistenceConflict before verifier
DISABLED user -> UserDisabled before verifier
ACTIVE user -> release session, then verify
```

No DB transaction/row lock is held during Kaiten verification.

## 21. Verification-before-persist ordering

Successful bind ordering:

```text
preflight user read
verifier.verify(...)
token_cipher.encrypt(...)
clock.now()
short write transaction
```

Verifier failures propagate and leave existing state unchanged. No encryption or write transaction is performed after verifier failure.

## 22. Encryption-before-write ordering

`TokenCipher.encrypt()` runs after successful verification and before the final locked transaction.

`CredentialEncryptionFailed` propagates as the crypto application error and leaves existing state unchanged.

## 23. Final locked write/re-check

Write methods use canonical lock order:

```text
users FOR UPDATE
kaiten_connections FOR UPDATE
```

`bind_or_replace_connection` re-checks the user under lock after verifier/encryption. If the user became disabled while verification was in flight, it raises `UserDisabled` and does not persist the credential.

## 24. First-bind behavior

If no connection exists under lock:

```text
create one kaiten_connections row
status ACTIVE
persist api_base_url, kaiten_user_id, workspace_id, encrypted_api_token,
token_encryption_version, last_verified_at
```

Integration tests prove the plaintext token is not persisted and ciphertext decrypts through the test cipher.

## 25. Replacement/re-enable behavior

Successful explicit bind for an existing `ACTIVE`, `NEEDS_REAUTH`, or `DISABLED` connection:

```text
updates the existing row
retains connection id
sets status ACTIVE
replaces api_base_url, external ids, ciphertext, crypto version, last_verified_at
```

The KVC user itself must be `ACTIVE`.

## 26. Concurrent replacement semantics

The implementation verifies/encrypts outside locks and serializes final writes through the parent user row followed by the connection row.

Test coverage includes deterministic sequential replacement simulation proving:

```text
one row remains
last serialized verified write wins
```

A stress timing race is deferred to `003-05`.

## 27. Repeated same-token semantics

The service treats repeated explicit verified bind as a new successful persistence event:

```text
one connection row
ACTIVE
valid current credential
new last_verified_at from Clock
possibly different Fernet ciphertext for same plaintext
```

It does not require identical ciphertext or unchanged snapshot.

## 28. `disable_connection`

Implemented:

```text
missing user -> PersistenceConflict
missing connection -> KaitenConnectionMissing
ACTIVE -> DISABLED
NEEDS_REAUTH -> DISABLED
DISABLED -> idempotent DISABLED result
disabled KVC user may disable safely
```

The method retains token bytes, crypto version, api base URL, external ids, and `last_verified_at`. It does not delete the row.

## 29. `get_active_connection_secret`

Implemented:

```text
missing user -> PersistenceConflict
disabled user -> UserDisabled
missing connection -> KaitenConnectionMissing
DISABLED connection -> KaitenConnectionDisabled
NEEDS_REAUTH -> KaitenConnectionNeedsReauth
ACTIVE -> capture snapshot, decrypt, return ActiveKaitenConnectionSecret
```

The method performs local decrypt only and does not call the verifier.

## 30. Exact credential snapshot

Snapshot is exactly:

```text
connection_id
encrypted_api_token bytes
token_encryption_version
```

It does not use `updated_at`, a token hash, fingerprint, or logical credential revision.

## 31. `mark_needs_reauth`

Implemented:

```text
lock current connection row for user_id
missing connection -> None
compare current id + ciphertext + crypto version with snapshot
stale mismatch -> None
DISABLED -> idempotent DISABLED result
NEEDS_REAUTH -> idempotent NEEDS_REAUTH result
ACTIVE -> NEEDS_REAUTH
```

No user lock is taken in this method, no reason is persisted, and no verifier/network call occurs.

## 32. Stale-snapshot race proof

Integration test:

```text
bind token A
get_active_connection_secret -> snapshot A
bind token B with same crypto version
mark_needs_reauth(snapshot A)
```

Result:

```text
None
current connection remains ACTIVE
persisted token decrypts to B
```

## 33. Same crypto-version/different-ciphertext proof

The stale snapshot test keeps:

```text
A.token_encryption_version == B.token_encryption_version
```

but the ciphertext differs, so the stale mark is rejected. This proves `token_encryption_version` is not a credential revision.

## 34. Disable/mark race behavior

Both `disable_connection` and `mark_needs_reauth` serialize on the same connection row. Tests cover matching disabled snapshot behavior:

```text
DISABLED stays DISABLED
no reactivation
no transition to NEEDS_REAUTH
```

## 35. Bind/user-disable in-flight proof

Integration test uses a deterministic fake verifier that disables the user after preflight and before final write.

Result:

```text
UserDisabled
no credential row is created
```

This proves locked status re-check after external verification.

## 36. `last_verified_at` lifecycle

`last_verified_at` is set/updated only after successful verified bind/replacement/rebind using injected `Clock`.

Tests prove it is retained on:

```text
verifier failure
encryption failure
disable
mark_needs_reauth
```

## 37. External IDs lifecycle

On every successful bind/replacement, `kaiten_user_id` and `workspace_id` are replaced by the verifier result.

The concrete HTTP verifier returns:

```text
kaiten_user_id = str(current_user.id)
workspace_id = None
```

No stale workspace id is preserved when verifier result has `None`.

## 38. Repository changes

No production repository code was changed.

`KaitenConnectionRepository.update_connection()` already supports the required frozen fields:

```text
api_base_url
kaiten_user_id
workspace_id
encrypted_api_token
token_encryption_version
status
last_verified_at
```

Repository contract tests were extended only to assert `get_for_user_for_update()` uses `FOR UPDATE`.

## 39. Unit tests

Added:

```text
tests/unit/test_kaiten_connection_service.py
tests/unit/test_clock.py
```

Coverage:

```text
verifier/encrypt/clock happen before final row locks
disabled preflight rejects before verifier
encryption failure happens before final write transaction
UtcClock returns timezone-aware UTC
```

## 40. Provider adapter tests

Added:

```text
tests/unit/test_kaiten_credential_verifier.py
```

Coverage:

```text
success id parsing
request path /users/current
request-scoped Authorization header
no shared client header mutation
401/403 mapping
408/429/5xx mapping
timeout/transport mapping
unexpected 4xx mapping
malformed JSON/body contract mapping
token/body redaction in exceptions
```

## 41. PostgreSQL integration tests

Added:

```text
tests/integration/test_kaiten_connection_service_postgresql.py
```

Coverage:

```text
first bind
replacement
NEEDS_REAUTH/DISABLED rebind to ACTIVE
disabled KVC user bind rejection
user disabled in-flight re-check
verifier failure state preservation
encryption failure state preservation
active secret snapshot
decrypt failure propagation
get-secret state errors
missing user/connection errors
stale auth failure after replacement
current snapshot mark_needs_reauth
disabled snapshot mark behavior
disable lifecycle
deterministic last-writer replacement simulation
database baseline restoration
```

## 42. Locking/concurrency tests

Tests prove:

```text
provider verification completes before final row locks
encryption completes before final row locks
user status is re-checked under lock after verifier
replacement keeps one row and last serialized write wins
snapshot compare prevents stale auth failure from downgrading newer credential
```

No flaky sleep-based concurrency test was added. Broader stress acceptance is deferred to `003-05`.

## 43. Failure atomicity/state-preservation tests

Tests prove existing rows are unchanged after:

```text
KaitenAuthenticationFailed
KaitenTemporarilyUnavailable
KaitenVerificationFailed
CredentialEncryptionFailed
disabled user during in-flight bind
stale mark_needs_reauth
```

## 44. Secret/repr/error-redaction tests

Tests and implementation confirm:

```text
plaintext token is never persisted
public KaitenConnectionResult has no token/ciphertext/snapshot
ActiveKaitenConnectionSecret repr hides plaintext and snapshot
KaitenCredentialSnapshot repr hides ciphertext
verifier exceptions hide synthetic token and raw response body
Authorization header is not persisted/logged
```

No logging was introduced.

## 45. PostgreSQL baseline restoration

Explicit DB state before full test run:

```text
current_database=kvc_dev
alembic_version=00201_mvp_service_model
dialog_sessions=0
kaiten_connections=0
max_chats=0
notification_history=0
notification_settings=0
pending_commands=0
users=0
```

Final DB state after tests:

```text
current_database=kvc_dev
alembic_version=00201_mvp_service_model
dialog_sessions=0
kaiten_connections=0
max_chats=0
notification_history=0
notification_settings=0
pending_commands=0
users=0
```

Cleanup targets only synthetic user ids created by tests. No broad truncate/delete was used.

## 46. No schema/dependency changes

Confirmed:

```text
no model/schema changes
no Alembic revision
no dependency change
no configuration change
no environment/example change
no local Kaiten content cache
no plaintext token column
```

## 47. Alembic current/check

Final Alembic diagnostics:

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

## 48. Targeted gate

Targeted command:

```text
.venv\Scripts\python.exe -m pytest tests\unit\test_kaiten_credential_verifier.py tests\unit\test_clock.py tests\unit\test_kaiten_connection_service.py tests\unit\test_repository_contracts.py tests\integration\test_kaiten_connection_service_postgresql.py tests\unit\test_imports.py -v
```

Initial targeted run found a test bug: an assertion referenced `verifier` without passing it into the service. The test was corrected.

Final targeted result:

```text
collected 64 items
64 passed in 7.08s
```

## 49. Full quality gate

Final full gate before this report:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
208 passed in 10.90s

.venv\Scripts\python.exe -m pytest -W error
208 passed in 10.76s

.venv\Scripts\python.exe -m ruff format --check .
106 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 44 source files

git diff --check
<no output, exit code 0>
```

Post-report verification:

```text
.venv\Scripts\python.exe -m ruff format --check .
107 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

git diff --check
<no output, exit code 0>
```

## 50. Changed-file classification

Application production code:

```text
src/kvc_application/__init__.py
src/kvc_application/services/__init__.py
src/kvc_application/services/kaiten_connection.py
```

Integration production code:

```text
src/kvc_integrations/kaiten/__init__.py
src/kvc_integrations/kaiten/credential_verifier.py
src/kvc_integrations/system/__init__.py
src/kvc_integrations/system/clock.py
```

Persistence repositories:

```text
unchanged production code
```

Configuration:

```text
none
```

Tests:

```text
tests/unit/test_imports.py
tests/unit/test_repository_contracts.py
tests/unit/test_kaiten_credential_verifier.py
tests/unit/test_kaiten_connection_service.py
tests/unit/test_clock.py
tests/integration/test_kaiten_connection_service_postgresql.py
```

Alembic/schema:

```text
none
```

Dependencies:

```text
none
```

Environment/example:

```text
none
```

Prompts:

```text
codex/prompts/003_04_kaiten_connection_service_implementation_prompt.md
```

Reports:

```text
codex/reports/003_04_kaiten_connection_service_implementation_report.md
```

Database final state:

```text
current_database=kvc_dev
alembic_version=00201_mvp_service_model
all seven business tables contain 0 rows
```

Other:

```text
none
```

## 51. Explicit deferred work

Deferred to `003-05`:

```text
full application-service acceptance
integrated audit of 003-01..003-04
optional decision on safe read-only live Kaiten verifier probe
broader concurrency acceptance
```

Deferred to `003-06`:

```text
branch acceptance
explicit staging/commit
Git closeout/integration
```

Future branches:

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

## 52. Final Git status/diff

Before this report was created:

```text
 M src/kvc_application/__init__.py
 M src/kvc_application/services/__init__.py
 M src/kvc_integrations/kaiten/__init__.py
 M tests/unit/test_imports.py
 M tests/unit/test_repository_contracts.py
?? codex/prompts/003_04_kaiten_connection_service_implementation_prompt.md
?? src/kvc_application/services/kaiten_connection.py
?? src/kvc_integrations/kaiten/credential_verifier.py
?? src/kvc_integrations/system/
?? tests/integration/test_kaiten_connection_service_postgresql.py
?? tests/unit/test_clock.py
?? tests/unit/test_kaiten_connection_service.py
?? tests/unit/test_kaiten_credential_verifier.py
```

Tracked diff before this report:

```text
src/kvc_application/__init__.py          | 3 ++-
src/kvc_application/services/__init__.py | 2 ++
src/kvc_integrations/kaiten/__init__.py  | 4 +++-
tests/unit/test_imports.py               | 1 +
tests/unit/test_repository_contracts.py  | 8 ++++++++
5 files changed, 16 insertions(+), 2 deletions(-)
```

Untracked source/test/prompt/report files are listed in `git status --short`.

## 53. Final status

```text
IMPLEMENTED - READY FOR 003-05 FULL APPLICATION SERVICE ACCEPTANCE
```
