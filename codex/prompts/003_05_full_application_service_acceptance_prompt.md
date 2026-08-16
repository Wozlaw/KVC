# 003-05 — Full application service acceptance

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
003-04   KaitenConnectionService + verifier + lifecycle implementation
```

Финальный статус `003-04`:

```text
IMPLEMENTED - READY FOR 003-05 FULL APPLICATION SERVICE ACCEPTANCE
```

Основной отчёт предыдущего этапа:

```text
codex/reports/003_04_kaiten_connection_service_implementation_report.md
```

Этот этап является **полной автоматизированной и интеграционной приёмкой application-service слоя ветки `003`**.

На `003-05` не проектировать новую архитектуру и не расширять продуктовый scope.

---

# 1. Главная цель

Доказать целостность всей цепочки:

```text
PRIVATE MAX identity
        ↓
IdentityService
        ↓
KVC user
        ↓
explicit Kaiten credential
        ↓
KaitenConnectionService
        ↓
Kaiten credential verification
        ↓
VersionedFernetTokenCipher
        ↓
encrypted PostgreSQL persistence
        ↓
safe credential retrieval
        ↓
stale-safe NEEDS_REAUTH lifecycle
```

После `003-05` должно быть доказано, что application layer готов к transport/integration development без скрытых архитектурных развилок.

Целевой финальный статус:

```text
ACCEPTED - READY FOR 003-06 BRANCH CLOSEOUT
```

---

# 2. Нормативные документы

Перед приёмкой изучи:

```text
codex/reports/003_00_application_service_user_onboarding_audit_report.md
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
codex/reports/003_04_kaiten_connection_service_implementation_report.md
```

Также обязательно сверить:

```text
codex/reports/002_03_repository_query_contracts_implementation_report.md
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

и фактический код:

```text
src/kvc_application/
src/kvc_integrations/security/
src/kvc_integrations/kaiten/
src/kvc_integrations/system/
src/kvc_persistence/
src/kvc_config/
tests/
pyproject.toml
.env.example
```

Приоритет:

```text
003-00a frozen specification
    >
accepted implementation reports 003-01..003-04
    >
accepted persistence baseline 002
    >
current prompt
```

---

# 3. Scope `003-05`

В scope:

```text
checkpoint принятого 003-04
full automated test gate
cross-service PostgreSQL acceptance
application-service contract audit
locking/concurrency acceptance
transaction atomicity acceptance
idempotency acceptance
security/redaction acceptance
crypto-version/credential-snapshot acceptance
read-only live Kaiten verifier probe
Git/worktree audit
final acceptance report
```

Out of scope:

```text
MAX bot transport
MAX polling/webhook
Kaiten card/board command implementation
Kaiten card mutations
attachments/photos
comments/deadlines
GigaChat
STT
dialog resolver
PendingCommand workflow
notification worker
production deployment wiring
new schema
new migration
new product states
new external dependencies
branch merge
push
```

---

# 4. Critical rule: acceptance, not feature development

`003-05` не должен превращаться в ещё один implementation stage.

Разрешено:

```text
acceptance tests
test harness improvements
read-only diagnostics
minimal test-only synchronization helpers
report documentation
```

Production code изменять **не следует**, если только приёмка не обнаружит реальный дефект уже реализованного frozen contract.

Если найден production defect:

1. не расширять scope;
2. зафиксировать конкретный failing contract;
3. выполнить только минимальное correction, если оно однозначно следует из frozen specification;
4. добавить regression test;
5. явно классифицировать correction в report.

Если исправление требует нового архитектурного решения:

```text
BLOCKED - FROZEN CONTRACT CONFLICT
```

---

# 5. Git checkpoint принятого `003-04`

`003-04` принят пользователем, но его код/report должны быть зафиксированы до `003-05`.

## 5.1. Initial inspection

Выполнить:

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

Expected previous checkpoint:

```text
6294a07 feat: add versioned token cipher adapter
```

Использовать фактический HEAD как источник истины.

---

# 6. Expected accepted `003-04` inventory

Ожидаемо в checkpoint `003-04` входят:

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

Текущий `003-05` prompt:

```text
codex/prompts/003_05_full_application_service_acceptance_prompt.md
```

не включать в checkpoint `003-04`.

---

# 7. Pre-checkpoint quality gate

Перед staging:

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

Accepted `003-04` reference:

```text
Python 3.12.9
pytest = 208 passed
pytest -W error = 208 passed
targeted = 64 passed
ruff PASS
mypy PASS
pip check PASS
Alembic current = 00201_mvp_service_model
Alembic check = no new upgrade operations
```

Если текущий untracked `003-05` prompt единственный мешает `ruff format --check .`, минимально форматировать prompt, но не включать его в checkpoint.

---

# 8. Pre-checkpoint secret audit

Проверить candidate files `003-04`.

Не должно быть реальных:

```text
Kaiten token
Authorization value
Bearer token
Fernet key
database password
MAX identity
private card/workspace data
```

Не печатать secret-like строки.

`.env` остаётся ignored и unstaged.

Если найден реальный секрет:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

---

# 9. Explicit staging and checkpoint

Не использовать:

```text
git add .
```

Явно проиндексировать только принятый `003-04`.

Проверить:

```powershell
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
git status --short
```

Если inventory корректен:

```powershell
git commit -m "feat: add Kaiten connection service"
```

После commit:

```powershell
git log --oneline --decorate -7
git status --short
git diff --check
```

Зафиксировать SHA в report.

После checkpoint допустимым dirty artifact является текущий:

```text
codex/prompts/003_05_full_application_service_acceptance_prompt.md
```

---

# 10. Baseline после checkpoint

До создания acceptance tests записать:

```powershell
git branch --show-current
git log --oneline --decorate -7
git status --short

.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src
.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

Это baseline `003-05`.

---

# 11. Development PostgreSQL safety

Перед любым acceptance DML подтвердить:

```text
KVC_APP_ENV == development
current_database() == kvc_dev
alembic_version == 00201_mvp_service_model
```

Записать исходные row counts:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

Не предполагать, что counts равны нулю.

Если пользователь добавил development data:

```text
сохранить baseline
использовать synthetic scoped rows
вернуть counts точно к baseline
```

Запрещено:

```text
TRUNCATE
DELETE без synthetic scope
cleanup чужих development rows
DDL
migration
```

---

# 12. Acceptance suite placement

Предпочтительно создать отдельный интегральный acceptance file:

```text
tests/integration/test_application_service_acceptance_postgresql.py
```

Допустимо несколько файлов, если это соответствует текущей test architecture, но не создавать десятки мелких acceptance files без необходимости.

Acceptance suite должна использовать **реальные production application services**:

```text
IdentityService
KaitenConnectionService
VersionedFernetTokenCipher
```

и реальные:

```text
PostgreSQL repositories
AsyncSession
```

Kaiten HTTP verifier для DB flow можно заменять deterministic fake, кроме отдельного HTTP adapter/live-probe acceptance.

---

# 13. End-to-end application lifecycle acceptance

Обязательный сквозной сценарий:

```text
1. Resolve unknown MAX identity.
2. KVC user created ACTIVE.
3. PRIVATE MAX binding created.
4. notification_settings created disabled.
5. Bind verified Kaiten credential A.
6. Connection ACTIVE.
7. get_active_connection_secret returns A + snapshot A.
8. mark_needs_reauth(snapshot A).
9. Connection NEEDS_REAUTH.
10. Explicit verified rebind credential B.
11. Same connection row becomes ACTIVE.
12. get_active_connection_secret returns B + snapshot B.
13. disable_connection.
14. Connection DISABLED.
15. Explicit verified rebind credential C.
16. Connection ACTIVE.
```

Assert invariants after every phase.

---

# 14. Cross-service identity isolation

Create two synthetic KVC identities:

```text
U1 / MAX1
U2 / MAX2
```

Bind separate Kaiten credentials.

Prove:

```text
user1 connection belongs only to user1
user2 connection belongs only to user2
identity rotation of U1 does not affect U2
disable U1 connection does not affect U2
mark_needs_reauth U1 cannot modify U2
```

No cross-user leakage.

---

# 15. Cross-service disabled-user acceptance

Flow:

```text
1. onboard ACTIVE user
2. bind Kaiten
3. set KVC user DISABLED through accepted persistence/admin primitive
4. resolve MAX identity
```

Expected:

```text
IdentityService still returns user_status=DISABLED
```

Then:

```text
bind_or_replace_connection -> UserDisabled
get_active_connection_secret -> UserDisabled
disable_connection -> allowed safe/idempotent
```

No automatic re-enable.

---

# 16. Notification default acceptance

During first-message onboarding prove exactly:

```text
notification_settings row exists
enabled = false
due_soon_days = 1
timezone = UTC
```

Repeated identity resolution:

```text
does not create duplicate settings
does not mutate settings
```

Safe MAX rotation:

```text
does not create duplicate settings
```

---

# 17. MAX rotation + Kaiten connection acceptance

Flow:

```text
1. onboard max_user_id U1 / max_chat_id C1
2. bind Kaiten
3. resolve U1 with new free chat C2
```

Expected:

```text
same KVC user_id
same MAX binding id
same Kaiten connection row
connection remains ACTIVE
token unchanged
chat id becomes C2
```

Identity transport rotation must not affect credential lifecycle.

---

# 18. Identity conflict + connection isolation

Prepare:

```text
U1/C1 -> KVC1 -> connection A
U2/C2 -> KVC2 -> connection B
```

Attempt:

```text
incoming U1/C2
```

Expected:

```text
IdentityConflict
```

After exception:

```text
both users unchanged
both bindings unchanged
both connections unchanged
both notification settings unchanged
```

This proves application transaction isolation across service boundaries.

---

# 19. Verify-before-persist acceptance

For existing ACTIVE connection A:

Test separately:

```text
KaitenAuthenticationFailed
KaitenTemporarilyUnavailable
KaitenVerificationFailed
CredentialEncryptionFailed
```

while attempting replacement B.

After each failure, prove byte-for-byte persistence invariants:

```text
same connection id
same api_base_url
same kaiten_user_id
same workspace_id
same encrypted_api_token
same token_encryption_version
same status
same last_verified_at
```

No partial mutation.

---

# 20. `last_verified_at` acceptance

Using deterministic UTC clock:

```text
T1 first bind
T2 successful replacement
```

Prove:

```text
first bind -> T1
successful replacement -> T2
```

And no change on:

```text
disable
mark_needs_reauth
stale mark
verifier failure
encryption failure
get_active_connection_secret
```

---

# 21. Credential snapshot acceptance

Mandatory proof:

```text
snapshot =
    connection_id
    + exact encrypted_api_token bytes
    + token_encryption_version
```

Do not use:

```text
updated_at
last_verified_at
plaintext token
hash/fingerprint
```

Assert DTO is immutable and repr-safe using already implemented contracts.

---

# 22. Same crypto version ≠ same credential

Mandatory acceptance:

```text
1. crypto active version = 1
2. bind plaintext A
3. capture snapshot A
4. bind plaintext B with same crypto version = 1
5. capture snapshot B
```

Assert:

```text
A.version == B.version == 1
A.connection_id == B.connection_id
A.ciphertext != B.ciphertext
snapshot A != snapshot B
```

Then:

```text
mark_needs_reauth(snapshot A) -> None
current B remains ACTIVE
```

This is a branch-level invariant and must be explicitly reported.

---

# 23. Current snapshot acceptance

For current ACTIVE snapshot:

```text
mark_needs_reauth(current)
```

Expected:

```text
ACTIVE -> NEEDS_REAUTH
```

Repeat same call:

```text
NEEDS_REAUTH -> NEEDS_REAUTH
```

No token mutation.

No `last_verified_at` mutation.

---

# 24. Disabled snapshot acceptance

Connection:

```text
DISABLED
```

with matching current snapshot.

Call:

```text
mark_needs_reauth
```

Expected:

```text
returns DISABLED result
state remains DISABLED
```

No resurrection.

---

# 25. Missing snapshot target acceptance

After connection is absent:

```text
mark_needs_reauth(...)
```

returns:

```text
None
```

No error framework expansion.

---

# 26. Crypto rotation integrated acceptance

Use two ephemeral test Fernet keys:

```text
version 1
version 2
```

Flow:

```text
1. create cipher config with active 1
2. bind credential A -> persisted version 1
3. create rotated cipher with keys {1,2}, active 2
4. decrypt/read old A through version 1
5. explicit rebind B -> persisted version 2
6. decrypt B through version 2
```

Prove old-key read compatibility.

Do not automatically re-encrypt version-1 rows on read.

---

# 27. Unknown crypto version acceptance

Create synthetic persistence state only inside controlled test transaction with:

```text
token_encryption_version not present in cipher
```

`get_active_connection_secret` should surface:

```text
CredentialDecryptionFailed
```

No status mutation.

Do not mark `NEEDS_REAUTH`.

No schema repair.

---

# 28. Tampered ciphertext acceptance

Within test-only synthetic row:

```text
alter encrypted_api_token bytes
keep known version
```

Then:

```text
get_active_connection_secret
```

Expected:

```text
CredentialDecryptionFailed
```

No automatic:

```text
delete
disable
NEEDS_REAUTH
```

This distinguishes local crypto-integrity failure from provider authentication failure.

---

# 29. Concurrency acceptance — onboarding

`003-02` has deterministic retry proof and DB uniqueness proof.

At `003-05`, attempt a true two-call concurrent scenario only if deterministic:

```python
await asyncio.gather(
    identity_service.resolve_or_onboard_private_max_user(input),
    identity_service.resolve_or_onboard_private_max_user(input),
)
```

Expected:

```text
same user_id
same binding_id
one user row
one binding row
one settings row
```

Use explicit synchronization/barriers if needed.

Do not use arbitrary sleeps.

If underlying scheduling cannot reliably force the race, retain the deterministic unit retry proof and classify this concurrent call as supplemental rather than required.

---

# 30. Concurrency acceptance — first bind/replacement

Create two already-verified logical flows using deterministic verifier coordination.

Goal:

```text
two concurrent successful binds/replacements for same ACTIVE KVC user
```

Required invariant:

```text
one kaiten_connections row
no unique violation exposed
valid ACTIVE final row
last serialized verified write wins
```

Use:

```text
asyncio.Event
explicit transaction coordination
```

not timing sleeps.

If deterministic service-level race cannot be forced without invasive production hooks, use repository lock tests + controlled transaction ordering and clearly report the limitation.

---

# 31. Concurrency acceptance — stale auth vs replacement

Mandatory deterministic ordering:

```text
T1 captures snapshot A
T2 explicit replacement persists B
T1 mark_needs_reauth(A)
```

Expected:

```text
B remains ACTIVE
```

Second ordering:

```text
T1 mark_needs_reauth(A) commits -> NEEDS_REAUTH
T2 explicit verified replacement B -> ACTIVE
```

Expected final:

```text
ACTIVE B
```

Both valid.

---

# 32. Concurrency acceptance — disable vs mark

Prove serial outcomes:

```text
disable first:
    DISABLED
    later matching mark -> DISABLED

mark first:
    NEEDS_REAUTH
    later disable -> DISABLED
```

Final explicit disable dominates.

---

# 33. Concurrency acceptance — user disabled during bind

Use deterministic verifier barrier:

```text
preflight user ACTIVE
verifier begins
another transaction sets user DISABLED
verifier completes
final write locks/re-checks user
```

Expected:

```text
UserDisabled
new credential not persisted
```

This scenario should already exist from `003-04`; `003-05` must include it in integrated acceptance result.

---

# 34. Canonical lock-order audit

Review production code and tests to confirm all multi-row mutation paths use:

```text
user FOR UPDATE
then
kaiten_connection FOR UPDATE
```

For:

```text
bind_or_replace_connection
disable_connection
get_active_connection_secret
```

`mark_needs_reauth` may lock connection only and must not subsequently lock user.

Document no reverse-order lock path.

If a reverse order exists:

```text
FAIL acceptance
```

and perform minimal correction if directly required by frozen specification.

---

# 35. No network under row lock audit

Prove:

```text
KaitenCredentialVerifier.verify
```

runs before the final lock transaction.

No provider HTTP call inside:

```text
session.begin()
FOR UPDATE wait
```

for bind/rebind.

`get_active_connection_secret` performs local decrypt only.

`mark_needs_reauth` performs no network call.

---

# 36. Application dependency audit

Inspect imports.

`kvc_application` must not depend on concrete:

```text
httpx
Fernet
KaitenHttpCredentialVerifier
VersionedFernetTokenCipher
AppSettings
MAX SDK
```

except that application services receive their Protocol dependencies.

Concrete adapters may depend on application ports/DTO/errors.

Direction must remain:

```text
application
    ← adapters implement ports
```

not:

```text
application imports adapters
```

Report result.

---

# 37. Repository transaction audit

Search/inspect all repositories involved:

```text
UserRepository
MaxChatRepository
NotificationSettingsRepository
KaitenConnectionRepository
```

Confirm no:

```text
session.commit()
session.rollback()
```

Application services remain transaction owners.

Any violation is acceptance failure.

---

# 38. Secret boundary audit

Verify production code has no path that:

```text
persists plaintext token
logs plaintext token
returns plaintext in public DTO
logs ciphertext
logs key material
puts token in URL/query
mutates shared HTTP client Authorization
stores raw Kaiten current-user JSON
```

`ActiveKaitenConnectionSecret` is internal only.

`KaitenConnectionResult` stays non-secret.

---

# 39. Error taxonomy acceptance

Cross-check all frozen errors are used coherently.

Identity layer:

```text
IdentityConflict
PersistenceConflict
```

Connection state:

```text
UserDisabled
KaitenConnectionMissing
KaitenConnectionDisabled
KaitenConnectionNeedsReauth
```

Provider:

```text
KaitenAuthenticationFailed
KaitenTemporarilyUnavailable
KaitenVerificationFailed
```

Crypto:

```text
CredentialEncryptionFailed
CredentialDecryptionFailed
```

Do not add new application error classes on acceptance unless frozen implementation is impossible without them.

Raw:

```text
SQLAlchemy errors
httpx exceptions
cryptography exceptions
provider response errors
```

must not cross the application boundary in normal expected flows.

---

# 40. Read-only live Kaiten verifier probe

After all offline automated acceptance passes, perform one **optional-but-recommended read-only live verifier probe** only if safe configured live values are already available locally.

Use existing local environment/settings values; do not ask the user to paste a token into report or command output.

Required prerequisites:

```text
KVC_APP_ENV == development
KVC_KAITEN_API_BASE_URL configured
KVC_KAITEN_API_TOKEN configured
```

Do not display values.

The probe must perform only:

```text
GET {KVC_KAITEN_API_BASE_URL.rstrip("/")}/users/current
```

with:

```text
Authorization: Bearer <configured token>
```

No POST/PATCH/PUT/DELETE.

No card lookup required.

No mutation.

---

# 41. Live probe implementation discipline

Prefer to invoke the actual production:

```text
KaitenHttpCredentialVerifier
```

with:

```text
httpx.AsyncClient
```

rather than a custom curl snippet, so the live probe validates the adapter actually implemented.

Load secret safely through local config/environment.

Do not:

```text
print token
print Authorization header
print full JSON response
write response JSON to report
persist response
```

Only safe output:

```text
HTTP/application outcome
normalized kaiten_user_id present
workspace_id is None
```

The normalized ID itself does not need to be written to report.

Preferred report:

```text
live verifier probe: PASS
credential accepted: yes
normalized Kaiten user id obtained: yes
workspace_id: None
mutation performed: no
```

---

# 42. Live probe failure semantics

If no live config is present:

```text
SKIPPED - LIVE CREDENTIALS NOT CONFIGURED
```

This alone does not fail `003-05` because all core acceptance is offline/deterministic.

If configured token is rejected:

```text
FAIL - LIVE KAITEN AUTHENTICATION
```

Do not expose token.

If provider/network temporarily unavailable:

```text
LIVE PROBE INCONCLUSIVE - KAITEN TEMPORARILY UNAVAILABLE
```

Do not rewrite application code merely because the internet/provider is temporarily unavailable.

If endpoint contract differs from adapter expectation:

```text
FAIL - LIVE KAITEN VERIFIER CONTRACT MISMATCH
```

and investigate before branch closeout.

---

# 43. 401 vs 403 observation

Current frozen adapter maps:

```text
401
403
```

to:

```text
KaitenAuthenticationFailed
```

Do not deliberately provoke 401/403 using fake live credentials.

The live probe uses only the configured valid credential.

If a valid configured credential unexpectedly returns `403`:

```text
record exact safe status only
do not expose response body
```

Treat it as:

```text
LIVE VERIFIER CONTRACT REVIEW REQUIRED
```

Do not redesign the error taxonomy automatically on this stage unless a deterministic documented contradiction to frozen semantics is established.

---

# 44. No live mutation acceptance

Explicitly assert in report:

```text
live calls made:
GET /users/current only
```

or:

```text
live probe skipped
```

There must be no:

```text
POST
PATCH
PUT
DELETE
```

to Kaiten.

Do not create a test card.

Do not add comments.

Do not alter deadlines.

---

# 45. HTTP adapter offline acceptance

Regardless of live probe availability, rerun deterministic provider tests for:

```text
200
401
403
408
429
5xx
timeout
transport error
malformed JSON
missing id
invalid id
```

The live probe supplements these tests; it does not replace them.

---

# 46. Full application package import smoke

Test importability:

```python
from kvc_application import (
    IdentityService,
    KaitenConnectionService,
)
```

and concrete adapters:

```python
from kvc_integrations.security import VersionedFernetTokenCipher
from kvc_integrations.kaiten import KaitenHttpCredentialVerifier
from kvc_integrations.system import UtcClock
```

No startup side effects.

No settings/key requirement merely from import.

---

# 47. Startup compatibility acceptance

Generic:

```text
AppSettings
FastAPI health/import
worker package import
```

must still succeed without:

```text
KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION
KVC_TOKEN_ENCRYPTION_KEYS
```

until production cipher is explicitly built.

Do not wire crypto construction into generic import side effects during acceptance.

---

# 48. `.env.example` acceptance

Confirm:

```text
KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION=
KVC_TOKEN_ENCRYPTION_KEYS=
```

or equivalent safe placeholders remain present.

No valid key material.

Existing development live Kaiten variables may remain as previously accepted, but no real secret values are tracked.

`.env` ignored.

---

# 49. No schema drift

Required:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

Expected:

```text
00201_mvp_service_model (head)
No new upgrade operations detected.
```

Also inspect:

```text
git diff -- alembic/ src/kvc_persistence/models.py
```

No unexpected schema modification.

---

# 50. Targeted `003-05` acceptance gate

Run new integrated acceptance tests plus critical existing suites.

Example:

```powershell
.venv\Scripts\python.exe -m pytest `
  tests/integration/test_application_service_acceptance_postgresql.py `
  tests/integration/test_identity_service_postgresql.py `
  tests/integration/test_kaiten_connection_service_postgresql.py `
  tests/unit/test_kaiten_connection_service.py `
  tests/unit/test_kaiten_credential_verifier.py `
  tests/unit/test_token_cipher_adapter.py `
  -v
```

Adapt actual paths.

Record:

```text
collected
passed
skipped
warnings
```

---

# 51. Full quality gate

After acceptance tests:

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
test count >= 208
pytest PASS
pytest -W error PASS
Ruff PASS
mypy PASS
pip check PASS
Alembic current = 00201_mvp_service_model
Alembic check = no drift
```

---

# 52. PostgreSQL final-state restoration

После всех offline/integration acceptance tests повторно получить:

```text
current_database
alembic_version
row counts
```

Ожидается:

```text
counts == exact starting baseline
```

Не обязательно zero.

Если synthetic rows остались:

```text
acceptance FAIL
```

Исправить только test cleanup, не удаляя user-created data.

---

# 53. Diff scope audit

Ожидаемые изменения `003-05` после checkpoint:

```text
tests/integration/test_application_service_acceptance_postgresql.py
possibly test-only helpers
codex/prompts/003_05_full_application_service_acceptance_prompt.md
codex/reports/003_05_full_application_service_acceptance_report.md
```

Production code:

```text
expected none
```

Если production code изменён:

```text
report must identify exact frozen-contract defect
show failing test before fix
show minimal correction
show regression test
```

---

# 54. No dependency changes

Expected:

```text
pyproject.toml unchanged
```

Do not add:

```text
stress-test library
retry library
HTTP helper
crypto library
```

Use existing toolchain.

---

# 55. Secret audit before report

Проверить:

```text
new acceptance tests
current prompt
report
any production correction
Git diff
```

Не должно быть:

```text
real Kaiten token
real Fernet key
Authorization value
database password
private card data
```

Runtime ephemeral keys generated in tests are preferred.

Live verifier report must not contain normalized real user ID unless there is a concrete reason; presence can simply be recorded as yes/no.

---

# 56. Report

Создай:

```text
codex/reports/003_05_full_application_service_acceptance_report.md
```

Минимальная структура:

1. Executive summary.
2. Acceptance scope.
3. Frozen sources and precedence.
4. Initial Git/worktree state.
5. Pre-checkpoint `003-04` gate.
6. `003-04` secret/diff audit.
7. Exact staged `003-04` inventory.
8. `003-04` checkpoint SHA/message.
9. Post-checkpoint state.
10. `003-05` baseline.
11. PostgreSQL starting baseline.
12. Application architecture/dependency audit.
13. Repository transaction-ownership audit.
14. Full lifecycle acceptance.
15. Cross-user isolation acceptance.
16. Disabled-user acceptance.
17. Notification defaults acceptance.
18. MAX rotation + connection isolation.
19. Identity conflict state preservation.
20. Verify-before-persist state preservation.
21. `last_verified_at` lifecycle.
22. Credential snapshot contract.
23. Same-version/different-credential proof.
24. Current snapshot NEEDS_REAUTH proof.
25. Disabled snapshot proof.
26. Crypto rotation integration.
27. Unknown-version crypto failure.
28. Tampered-ciphertext failure.
29. Onboarding concurrency acceptance.
30. Bind/replacement concurrency acceptance.
31. Stale-auth/replacement ordering.
32. Disable/mark ordering.
33. In-flight user-disable proof.
34. Lock-order audit.
35. No-network-under-lock audit.
36. Error taxonomy audit.
37. Secret boundary audit.
38. Import/startup compatibility.
39. Offline verifier acceptance.
40. Live read-only verifier probe.
41. Explicit live mutation statement.
42. PostgreSQL final baseline.
43. Alembic/schema audit.
44. Targeted acceptance gate.
45. Full quality gate.
46. Production code changes, if any.
47. Changed-file classification.
48. Secret audit.
49. Remaining risks.
50. Readiness for `003-06`.
51. Final Git status/diff.
52. Final status.

---

# 57. Report: production correction policy

If no production code changed:

```text
Production corrections:
none
```

If changed, list:

```text
failing contract
failing test
root cause
minimal correction
regression test
why no architecture decision was required
```

Do not hide acceptance-stage bug fixes.

---

# 58. Changed-file classification

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
Live external effects:
Database final state:
Other:
```

Expected:

```text
Application production code:
none

Integration production code:
none

Persistence repositories:
none

Configuration:
none

Alembic/schema:
none

Dependencies:
none

Live external effects:
GET /users/current only, or skipped
```

---

# 59. Acceptance criteria — Git checkpoint

- branch is `003-application-service-user-onboarding`;
- accepted `003-04` gate passes;
- accepted `003-04` secret audit clean;
- accepted `003-04` explicitly staged;
- `003-05` prompt excluded;
- checkpoint commit created;
- recommended message:
  - `feat: add Kaiten connection service`;
- checkpoint SHA recorded;
- no unexplained accepted-stage residue after commit.

---

# 60. Acceptance criteria — identity layer

- new PRIVATE identity creates ACTIVE user;
- one primary PRIVATE MAX binding;
- notification settings created atomically;
- defaults exactly false / 1 / UTC;
- repeated identity resolution idempotent;
- safe MAX chat rotation preserves user/binding identity;
- conflicting identity raises `IdentityConflict`;
- disabled identity still resolves;
- exactly-one retry semantics remain covered;
- no cross-user state mutation.

---

# 61. Acceptance criteria — crypto layer

- Fernet authenticated encryption;
- exact version selects exact key;
- active version used for writes;
- old versions remain readable when configured;
- no MultiFernet trial fallback;
- key material external;
- no plaintext/ciphertext/key repr leaks;
- same crypto version can represent different credential snapshots;
- unknown version fails as `CredentialDecryptionFailed`;
- tampered ciphertext fails as `CredentialDecryptionFailed`.

---

# 62. Acceptance criteria — Kaiten connection layer

- verifier outside locks;
- encryption outside write locks;
- missing/disabled user guards;
- first bind creates one ACTIVE row;
- replacement retains same connection id;
- NEEDS_REAUTH rebind -> ACTIVE;
- DISABLED connection explicit rebind -> ACTIVE;
- disabled KVC user cannot rebind;
- failed verification leaves current row unchanged;
- failed encryption leaves current row unchanged;
- disable idempotent;
- active secret state errors correct;
- current credential decrypts;
- stale mark cannot downgrade new credential.

---

# 63. Acceptance criteria — concurrency/locking

- canonical lock order verified;
- no network under row lock;
- parent user serialization for bind/replacement;
- one connection per user invariant;
- stale snapshot compare safe;
- disable cannot resurrect;
- explicit later bind can re-enable connection if KVC user ACTIVE;
- KVC user disable prevents in-flight bind write;
- no arbitrary sleep-based flaky acceptance;
- no distributed locks.

---

# 64. Acceptance criteria — provider verifier

Offline:

- request = GET `/users/current`;
- request-scoped Bearer auth;
- no token URL/query;
- 200 valid id accepted;
- 401/403 auth mapping;
- 408/429/5xx/transport timeout temporary mapping;
- malformed/unexpected provider response verification mapping;
- token/body redaction.

Live, when configured:

- only GET `/users/current`;
- production verifier used;
- no response body persisted/reported;
- credential accepted or safe outcome classified;
- zero mutations.

---

# 65. Acceptance criteria — security

- no plaintext token persistence;
- no plaintext token public result;
- no ciphertext public result;
- no key material in DB/Git;
- no raw provider JSON persistence;
- no Authorization logging;
- no real credentials in tests/report;
- `.env` ignored;
- live token never printed;
- secret audit PASS.

---

# 66. Acceptance criteria — infrastructure

- no new schema;
- no migration;
- no dependency addition;
- PostgreSQL final counts equal starting baseline;
- Alembic current remains `00201_mvp_service_model`;
- Alembic check no drift;
- targeted acceptance PASS;
- full pytest PASS;
- `pytest -W error` PASS;
- Ruff PASS;
- mypy PASS;
- pip check PASS;
- `git diff --check` PASS.

---

# 67. Final status

If all core offline/database acceptance passes and live probe passes or is legitimately skipped:

```text
ACCEPTED - READY FOR 003-06 BRANCH CLOSEOUT
```

If core frozen behavior fails but can be corrected unambiguously during acceptance:

```text
ACCEPTED AFTER CORRECTION - READY FOR 003-06 BRANCH CLOSEOUT
```

and report exact correction.

If live probe is temporarily unavailable while all deterministic acceptance passes:

```text
ACCEPTED WITH LIVE PROBE INCONCLUSIVE - READY FOR 003-06
```

only if failure is clearly transient provider/network availability and not adapter contract mismatch.

If live configured endpoint/credential exposes a real adapter contract mismatch:

```text
BLOCKED - LIVE KAITEN VERIFIER CONTRACT MISMATCH
```

If frozen architecture itself is inconsistent:

```text
BLOCKED - FROZEN CONTRACT CONFLICT
```

If real secret is found:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

Do not perform `003-06` inside this prompt.

---

## Главное правило этапа

`003-05` не строит новый функционал.

Он должен доказать, что уже реализованная ветка `003` является одной согласованной системой:

```text
MAX identity
+
KVC user lifecycle
+
encrypted Kaiten credential lifecycle
+
PostgreSQL transaction boundaries
+
exact crypto versions
+
stale credential protection
```

и что следующий шаг может быть исключительно:

```text
003-06 — branch acceptance / Git integration / closeout
```
