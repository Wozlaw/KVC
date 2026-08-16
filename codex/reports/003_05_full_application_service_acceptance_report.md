# 003-05 - Full application service acceptance report

## 1. Executive summary

Completed full automated and PostgreSQL-backed acceptance for branch `003` application-service layer:

```text
PRIVATE MAX identity -> IdentityService -> KVC user -> explicit Kaiten credential
-> KaitenConnectionService -> verifier -> VersionedFernetTokenCipher
-> encrypted PostgreSQL persistence -> safe secret retrieval
-> stale-safe NEEDS_REAUTH lifecycle
```

No production implementation was changed during `003-05`. The only code artifact added is the integration acceptance suite.

Final status:

```text
ACCEPTED - READY FOR 003-06 BRANCH CLOSEOUT
```

## 2. Acceptance scope

In scope:

```text
accepted 003-04 checkpoint
full automated gate
cross-service PostgreSQL acceptance
transaction/locking/concurrency acceptance
security/redaction audit
crypto-version and credential-snapshot acceptance
read-only live Kaiten verifier probe
Git/worktree audit
final report
```

Out of scope and not performed:

```text
MAX transport
Kaiten card/board commands or mutations
GigaChat/STT
dialog resolver
PendingCommand workflow
notification worker
schema migration
dependency change
push/merge
003-06 closeout
```

## 3. Frozen sources and precedence

Reviewed and used:

```text
codex/reports/003_00_application_service_user_onboarding_audit_report.md
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
codex/reports/003_04_kaiten_connection_service_implementation_report.md
codex/reports/002_03_repository_query_contracts_implementation_report.md
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

Precedence:

```text
003-00a frozen specification
accepted implementation reports 003-01..003-04
accepted persistence baseline 002
current 003-05 prompt
```

No frozen-contract conflict was found.

## 4. Initial Git/worktree state

Branch:

```text
003-application-service-user-onboarding
```

Initial post-checkpoint log for `003-05`:

```text
e4dbc66 (HEAD -> 003-application-service-user-onboarding) feat: add Kaiten connection service
6294a07 feat: add versioned token cipher adapter
e577ed9 feat: add identity onboarding service
f99b2c8 feat: add application service contracts
568a0bb (002-mvp-service-data-model) docs: close MVP service data model branch
4abdb91 feat: add persistence repository contracts
9cd4f91 feat: add MVP service persistence model
```

Post-checkpoint dirty artifact before acceptance work:

```text
?? codex/prompts/003_05_full_application_service_acceptance_prompt.md
```

## 5. Pre-checkpoint `003-04` gate

Before committing accepted `003-04`, the gate passed:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
208 passed in 11.49s

.venv\Scripts\python.exe -m pytest -W error
208 passed in 10.88s

.venv\Scripts\python.exe -m ruff format --check .
108 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 44 source files

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.

git diff --check
<no output, exit code 0>
```

## 6. `003-04` secret/diff audit

Candidate files were audited without printing secret-like matched lines.

Result:

```text
No real Kaiten token.
No Authorization/Bearer value.
No real Fernet key.
No database password.
No private card/workspace data.
```

Matches were limited to normative documentation, field names, and synthetic test markers.

## 7. Exact staged `003-04` inventory

Explicitly staged for `003-04`, without `git add .`:

```text
src/kvc_application/__init__.py
src/kvc_application/services/__init__.py
src/kvc_application/services/kaiten_connection.py
src/kvc_integrations/kaiten/__init__.py
src/kvc_integrations/kaiten/credential_verifier.py
src/kvc_integrations/system/__init__.py
src/kvc_integrations/system/clock.py
tests/unit/test_imports.py
tests/unit/test_repository_contracts.py
tests/unit/test_kaiten_credential_verifier.py
tests/unit/test_kaiten_connection_service.py
tests/unit/test_clock.py
tests/integration/test_kaiten_connection_service_postgresql.py
codex/prompts/003_04_kaiten_connection_service_implementation_prompt.md
codex/reports/003_04_kaiten_connection_service_implementation_report.md
```

Staged diff:

```text
15 files changed, 6086 insertions(+), 2 deletions(-)
```

The `003-05` prompt was excluded.

## 8. `003-04` checkpoint SHA/message

Created checkpoint:

```text
e4dbc66 feat: add Kaiten connection service
```

After checkpoint, `git diff --check` had no output.

## 9. Post-checkpoint state

After checkpoint, allowed dirty artifact:

```text
?? codex/prompts/003_05_full_application_service_acceptance_prompt.md
```

No tracked production diff existed before adding acceptance tests.

## 10. `003-05` baseline

Baseline gate before adding the acceptance suite:

```text
.venv\Scripts\python.exe -m pytest
208 passed in 10.71s

.venv\Scripts\python.exe -m pytest -W error
208 passed in 10.86s

.venv\Scripts\python.exe -m ruff format --check .
108 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 44 source files

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

## 11. PostgreSQL starting baseline

Safety prerequisites and starting counts:

```text
app_env=development
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

Acceptance DML used synthetic-scoped rows only.

## 12. Application architecture/dependency audit

Search in `src\kvc_application` for concrete provider/config/crypto dependencies produced no output:

```text
httpx
Fernet
KaitenHttpCredentialVerifier
VersionedFernetTokenCipher
AppSettings
get_settings
kvc_integrations
KVC_
```

Result:

```text
PASS - kvc_application remains bound to ports/services and not concrete adapters or settings.
```

## 13. Repository transaction-ownership audit

Search for repository/service transaction ownership violations:

```text
rg -n "\.commit\(|\.rollback\(" src\kvc_persistence\repositories src\kvc_application\services
<no output, exit code 1>
```

Result:

```text
PASS - repositories do not commit/rollback; application services own transaction boundaries.
```

## 14. Full lifecycle acceptance

Added:

```text
tests/integration/test_application_service_acceptance_postgresql.py
```

The suite uses real:

```text
IdentityService
KaitenConnectionService
VersionedFernetTokenCipher
PostgreSQL AsyncSession/sessionmaker
PostgreSQL repositories
```

The full lifecycle test proves:

```text
unknown PRIVATE MAX identity -> ACTIVE KVC user
default notification settings
bind credential A -> ACTIVE
get active secret + snapshot A
mark snapshot A -> NEEDS_REAUTH
explicit rebind B -> same row ACTIVE
disable -> DISABLED
explicit rebind C -> same row ACTIVE
```

Result:

```text
PASS
```

## 15. Cross-user isolation acceptance

Two synthetic identities and connections were exercised.

Proved:

```text
U1 connection belongs only to U1
U2 connection belongs only to U2
U1 MAX rotation does not affect U2
U1 disable does not affect U2
stale/mismatched U1-style reauth mark cannot modify U2
```

Result:

```text
PASS
```

## 16. Disabled-user acceptance

Flow covered:

```text
onboard ACTIVE user
bind Kaiten
set KVC user DISABLED through persistence primitive
resolve MAX identity
```

Expected and observed:

```text
IdentityService returns user_status=DISABLED
bind_or_replace_connection raises UserDisabled
get_active_connection_secret raises UserDisabled
disable_connection is allowed and idempotent
no automatic re-enable
```

Result:

```text
PASS
```

## 17. Notification defaults acceptance

First-message onboarding creates exactly one settings row:

```text
enabled=false
due_soon_days=1
timezone=UTC
```

Repeated resolution and safe MAX rotation do not duplicate or mutate the settings row.

Result:

```text
PASS
```

## 18. MAX rotation + connection isolation

Flow:

```text
U1/C1 -> bind Kaiten -> resolve U1/C2
```

Observed:

```text
same KVC user_id
same MAX binding id
same Kaiten connection row
connection remains ACTIVE
token/ciphertext unchanged
chat id becomes C2
```

Result:

```text
PASS
```

## 19. Identity conflict state preservation

Prepared:

```text
U1/C1 -> KVC1 -> connection A
U2/C2 -> KVC2 -> connection B
```

Attempted incoming `U1/C2`.

Observed:

```text
IdentityConflict
both users unchanged
both connections unchanged
both notification settings unchanged
```

Result:

```text
PASS
```

## 20. Verify-before-persist state preservation

For an existing ACTIVE connection, replacement failure cases were tested:

```text
KaitenAuthenticationFailed
KaitenTemporarilyUnavailable
KaitenVerificationFailed
CredentialEncryptionFailed
```

After each failure, the connection snapshot remained byte-for-byte unchanged:

```text
connection id
api_base_url
kaiten_user_id
workspace_id
encrypted_api_token
token_encryption_version
status
last_verified_at
```

Result:

```text
PASS
```

## 21. `last_verified_at` lifecycle

Using a deterministic UTC clock:

```text
first bind -> T1
successful replacement -> T2
```

No mutation was observed on:

```text
disable
mark_needs_reauth
stale mark
verifier failure
encryption failure
get_active_connection_secret
```

Result:

```text
PASS
```

## 22. Credential snapshot contract

The acceptance suite proves the snapshot is exactly:

```text
connection_id
encrypted_api_token bytes
token_encryption_version
```

It does not use:

```text
updated_at
last_verified_at
plaintext token
hash/fingerprint
```

DTO immutability and repr safety were asserted.

Result:

```text
PASS
```

## 23. Same-version/different-credential proof

With active crypto version `1`:

```text
credential A snapshot version == 1
credential B snapshot version == 1
same connection_id
ciphertext differs
snapshot A != snapshot B
mark_needs_reauth(snapshot A) returns None
current B remains ACTIVE
```

Result:

```text
PASS
```

## 24. Current snapshot NEEDS_REAUTH proof

For the current ACTIVE snapshot:

```text
mark_needs_reauth(current) -> ACTIVE to NEEDS_REAUTH
repeat same mark -> NEEDS_REAUTH remains NEEDS_REAUTH
```

No token bytes or `last_verified_at` mutation occurred.

Result:

```text
PASS
```

## 25. Disabled snapshot proof

For a DISABLED connection with matching current snapshot:

```text
mark_needs_reauth -> returns DISABLED result
state remains DISABLED
```

No resurrection and no transition to `NEEDS_REAUTH`.

Result:

```text
PASS
```

## 26. Crypto rotation integration

Integrated flow:

```text
version 1 key encrypts credential A
rotated key ring {1, 2} with active version 2 reads old A through version 1
explicit rebind B persists version 2
version 2 ciphertext decrypts through version 2
```

No automatic re-encryption on read.

Result:

```text
PASS
```

## 27. Unknown-version crypto failure

Synthetic persistence state with an unknown `token_encryption_version` was tested.

Observed:

```text
get_active_connection_secret raises CredentialDecryptionFailed
connection status remains ACTIVE
no NEEDS_REAUTH transition
no schema repair
```

Result:

```text
PASS
```

## 28. Tampered-ciphertext failure

Synthetic tampering of `encrypted_api_token` with a known version was tested.

Observed:

```text
get_active_connection_secret raises CredentialDecryptionFailed
connection status remains ACTIVE
no delete
no disable
no NEEDS_REAUTH
```

Result:

```text
PASS
```

## 29. Onboarding concurrency acceptance

The acceptance suite runs:

```text
asyncio.gather(
    resolve_or_onboard_private_max_user(input),
    resolve_or_onboard_private_max_user(input),
)
```

Observed:

```text
same user_id
same binding_id
one settings row
one binding row
```

Result:

```text
PASS
```

## 30. Bind/replacement concurrency acceptance

The acceptance suite runs two concurrent successful binds for the same ACTIVE KVC user.

Observed:

```text
one kaiten_connections row
no unique violation exposed
valid ACTIVE final row
final row belongs to one verified writer
```

No arbitrary sleeps were introduced.

Result:

```text
PASS
```

## 31. Stale-auth/replacement ordering

The stale snapshot scenario proves:

```text
old credential snapshot cannot downgrade a newer ACTIVE credential
mark_needs_reauth(old snapshot) returns None
```

This holds even when both credentials use the same crypto key version.

Result:

```text
PASS
```

## 32. Disable/mark ordering

`disable_connection` and `mark_needs_reauth` serialize on the current connection row.

Observed:

```text
disabled matching snapshot stays DISABLED
stale/missing snapshot target returns None where specified
no disabled connection resurrection
```

Result:

```text
PASS
```

## 33. In-flight user-disable proof

The acceptance suite uses a deterministic verifier that disables the KVC user after preflight and before the final write.

Observed:

```text
UserDisabled
new credential not persisted
```

Result:

```text
PASS
```

## 34. Lock-order audit

Production source audit:

```text
56: verifier.verify(...)
65: session.begin()
69: users.get_by_id_for_update(...)
75: connections.get_for_user_for_update(...)
107: session.begin()
111: users.get_by_id_for_update(...)
116: connections.get_for_user_for_update(...)
139: session.begin()
143: users.get_by_id_for_update(...)
149: connections.get_for_user_for_update(...)
178: session.begin()
181: connections.get_for_user_for_update(...)
```

Result:

```text
PASS - bind/disable/get-secret use user lock then connection lock.
PASS - mark_needs_reauth locks connection only and does not later lock user.
```

## 35. No-network-under-lock audit

Production source shows:

```text
KaitenCredentialVerifier.verify runs before final session.begin()
token encryption runs before final locked write transaction
get_active_connection_secret performs local decrypt only
mark_needs_reauth performs no network call
```

Result:

```text
PASS
```

## 36. Error taxonomy audit

Accepted errors remain coherent:

```text
IdentityConflict
PersistenceConflict
UserDisabled
KaitenConnectionMissing
KaitenConnectionDisabled
KaitenConnectionNeedsReauth
KaitenAuthenticationFailed
KaitenTemporarilyUnavailable
KaitenVerificationFailed
CredentialEncryptionFailed
CredentialDecryptionFailed
```

No new application error class was added in acceptance.

Result:

```text
PASS
```

## 37. Secret boundary audit

Acceptance confirms:

```text
plaintext token is not persisted
plaintext token is not returned by public result DTOs
ciphertext is not returned by public result DTOs
keys are not stored in DB/Git
raw provider JSON is not persisted
Authorization is request-scoped and not logged
shared HTTP client headers are not mutated
```

`ActiveKaitenConnectionSecret` remains an internal application workflow DTO.

Result:

```text
PASS
```

## 38. Import/startup compatibility

Import/startup smoke result without crypto env keys:

```text
imports=ok
crypto_active_version=None
crypto_keys=None
api_app=True
worker_import=True
symbols=True
```

`.env.example` contains safe placeholders:

```text
KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION=
KVC_TOKEN_ENCRYPTION_KEYS=
```

No old single-key `KVC_TOKEN_ENCRYPTION_KEY` placeholder is present.

Result:

```text
PASS
```

## 39. Offline verifier acceptance

Deterministic provider tests were rerun in the targeted gate.

Covered:

```text
200 success
401/403 authentication mapping
408/429/5xx temporary mapping
timeout
transport error
malformed JSON
missing id
invalid id
request-scoped Bearer auth
token/body redaction
```

Result:

```text
PASS
```

## 40. Live read-only verifier probe

The live probe used the production `KaitenHttpCredentialVerifier` with `httpx.AsyncClient`.

Safe output:

```text
live verifier probe: PASS
credential accepted: yes
normalized Kaiten user id obtained: True
workspace_id is None: True
live calls made: GET /users/current only
mutation performed: no
```

No token, Authorization header, raw JSON response, or normalized real user id was printed or stored.

## 41. Explicit live mutation statement

Live external effects:

```text
GET /users/current only
```

No live:

```text
POST
PATCH
PUT
DELETE
card lookup
card creation
comment
deadline mutation
```

Result:

```text
PASS
```

## 42. PostgreSQL final baseline

Final state after all acceptance tests:

```text
app_env=development
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

Counts equal the starting baseline.

## 43. Alembic/schema audit

Final Alembic checks:

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

Schema diff audit:

```text
git diff -- alembic.ini src\kvc_persistence\models.py src\kvc_persistence\migrations
<no output>
```

Result:

```text
PASS - no schema drift.
```

## 44. Targeted acceptance gate

Command:

```text
.venv\Scripts\python.exe -m pytest tests\integration\test_application_service_acceptance_postgresql.py tests\integration\test_identity_service_postgresql.py tests\integration\test_kaiten_connection_service_postgresql.py tests\unit\test_kaiten_connection_service.py tests\unit\test_kaiten_credential_verifier.py tests\unit\test_token_cipher_adapter.py -v
```

Final result:

```text
collected 104 items
104 passed in 10.72s
```

An initial targeted run exposed only a test-harness issue: the deterministic `FixedClock` in the new acceptance file exhausted supplied values in scenarios where repeated reads are expected to be time-neutral. The helper was corrected to repeat the last supplied value. No production code changed.

## 45. Full quality gate

Final sequential gate:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
225 passed in 14.38s

.venv\Scripts\python.exe -m pytest -W error
225 passed in 14.68s

.venv\Scripts\python.exe -m ruff format --check .
109 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 44 source files

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.

git diff --check
<no output, exit code 0>
```

Note: an attempted concurrent execution of `pytest` and `pytest -W error` against the same live PostgreSQL database produced expected false fixture baseline conflicts. The gate was rerun sequentially and passed. No manual cleanup was required; final DB counts returned to baseline.

Post-report verification:

```text
.venv\Scripts\python.exe -m ruff format --check .
110 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

git diff --check
<no output, exit code 0>
```

## 46. Production code changes, if any

Production corrections:

```text
none
```

No frozen-contract defect was found. The only correction was a test-only helper adjustment in the new acceptance suite.

## 47. Changed-file classification

Application production code:

```text
none
```

Integration production code:

```text
none
```

Persistence repositories:

```text
none
```

Configuration:

```text
none
```

Tests:

```text
tests/integration/test_application_service_acceptance_postgresql.py
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
codex/prompts/003_05_full_application_service_acceptance_prompt.md
```

Reports:

```text
codex/reports/003_05_full_application_service_acceptance_report.md
```

Live external effects:

```text
GET /users/current only
```

Database final state:

```text
counts equal starting baseline
```

Other:

```text
none
```

## 48. Secret audit

Pre-report audit command printed filenames only:

```text
rg -l -i "bearer|authorization|kaiten.*token|fernet|database_url|password|private card|workspace|plaintext|ciphertext|encrypted_api_token|KVC_KAITEN_API_TOKEN|KVC_KAITEN_API_BASE_URL" codex\prompts\003_05_full_application_service_acceptance_prompt.md tests\integration\test_application_service_acceptance_postgresql.py
```

Result:

```text
codex\reports\003_05_full_application_service_acceptance_report.md
tests\integration\test_application_service_acceptance_postgresql.py
codex\prompts\003_05_full_application_service_acceptance_prompt.md
```

Findings:

```text
No real Kaiten token.
No Authorization/Bearer value.
No real Fernet key.
No database password.
No private card/workspace data.
```

Matches are expected normative text, field names, and synthetic/ephemeral test values. `.env` remains ignored:

```text
!! .env
```

## 49. Remaining risks

Residual risks are outside `003-05` scope:

```text
MAX transport and user-facing command parsing still need their own acceptance.
Future notification worker must filter disabled users.
Future Kaiten command adapters must preserve explicit-command mutation policy.
Live verifier probe validates only GET /users/current, not future card/board APIs.
Live PostgreSQL acceptance tests must be run sequentially or isolated per database.
```

No risk blocks `003-06`.

## 50. Readiness for `003-06`

Branch `003` application-service layer is ready for closeout because:

```text
accepted 003-04 is checkpointed
cross-service PostgreSQL acceptance passes
full quality gate passes
live verifier probe passes
no schema/dependency drift
no production correction required
secrets audit clean
database restored to baseline
```

Do not start `003-06` inside this stage.

## 51. Final Git status/diff

Final status before this report was created:

```text
?? codex/prompts/003_05_full_application_service_acceptance_prompt.md
?? tests/integration/test_application_service_acceptance_postgresql.py
```

Tracked diff before report:

```text
git diff --stat
<no output>

git diff --name-status
<no output>
```

Expected status after report creation:

```text
?? codex/prompts/003_05_full_application_service_acceptance_prompt.md
?? codex/reports/003_05_full_application_service_acceptance_report.md
?? tests/integration/test_application_service_acceptance_postgresql.py
```

Observed post-report status:

```text
?? codex/prompts/003_05_full_application_service_acceptance_prompt.md
?? codex/reports/003_05_full_application_service_acceptance_report.md
?? tests/integration/test_application_service_acceptance_postgresql.py
```

## 52. Final status

```text
ACCEPTED - READY FOR 003-06 BRANCH CLOSEOUT
```
