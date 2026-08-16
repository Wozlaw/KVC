# 003-06 — Branch acceptance, Git integration and closeout

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Закрываемый функциональный этап:

```text
003 — Application service layer and user onboarding
```

Текущая рабочая ветка:

```text
003-application-service-user-onboarding
```

Этапы ветки `003` выполнены и приняты:

```text
003-00   Application service/user onboarding audit
003-00a  Final application service/user onboarding specification
003-01   Application DTO/port/error contracts implementation
003-02   IdentityService + MAX onboarding/rotation implementation
003-03   Versioned TokenCipher + crypto configuration implementation
003-04   KaitenConnectionService + verifier + lifecycle implementation
003-05   Full application-service acceptance
```

Основной входной отчёт:

```text
codex/reports/003_05_full_application_service_acceptance_report.md
```

Его финальный статус:

```text
ACCEPTED - READY FOR 003-06 BRANCH CLOSEOUT
```

На этом этапе необходимо **организационно и технически закрыть ветку `003`**.

Новый продуктовый функционал не добавлять.

---

# 1. Главная цель

Выполнить финальный closeout ветки `003`:

1. проверить текущий Git/worktree state;
2. повторно подтвердить принятый результат `003-05`;
3. явно зафиксировать acceptance suite `003-05` отдельным checkpoint commit;
4. провести полный audit diff ветки `003` относительно принятой ветки `002`;
5. проверить architecture/dependency boundaries;
6. проверить secret/privacy/config/schema hygiene;
7. подтвердить PostgreSQL final state;
8. повторно выполнить полный project gate **последовательно**, не параллельно;
9. создать closeout report;
10. зафиксировать `003-06` documentation closeout commit;
11. добиться clean worktree;
12. оставить финальный HEAD ветки `003` как точную базу следующей функциональной ветки.

На `003-06`:

```text
не открывать следующую ветку
не merge в main
не push
не rebase
не добавлять новую feature work
```

---

# 2. Нормативные документы

Перед closeout обязательно изучи:

```text
codex/reports/003_00_application_service_user_onboarding_audit_report.md
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
codex/reports/003_04_kaiten_connection_service_implementation_report.md
codex/reports/003_05_full_application_service_acceptance_report.md
```

Также сверить accepted persistence base:

```text
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

и фактический repository state:

```text
src/kvc_application/
src/kvc_integrations/
src/kvc_config/
src/kvc_persistence/
tests/
codex/prompts/
codex/reports/
pyproject.toml
.env.example
.gitignore
```

Приоритет:

```text
003-00a frozen specification
    >
accepted reports 003-01..003-05
    >
accepted branch 002 baseline
    >
current 003-06 prompt
```

Не пересматривать архитектурные решения `003`.

---

# 3. Frozen branch `003` scope

Ветка `003` должна содержать только уже принятый application-service/user-onboarding foundation:

```text
application DTOs
application errors
application ports

IdentityService
PRIVATE MAX identity onboarding
safe MAX chat rotation
eager notification settings creation
onboarding race handling

VersionedFernetTokenCipher
versioned external key configuration
TokenCipher configuration parser/factory

KaitenHttpCredentialVerifier
UtcClock
KaitenConnectionService
bind/rebind/disable
active credential retrieval
stale-safe NEEDS_REAUTH lifecycle

minimal repository extension for safe MAX rotation

unit tests
PostgreSQL integration tests
full application-service acceptance suite
branch prompts/reports
```

Не добавлять на closeout:

```text
MAX bot transport
MAX polling/webhook
Kaiten card/board command adapter
comments/deadlines/photos
GigaChat
STT
dialog resolver
PendingCommand orchestration
notification worker
new persistence tables
new migration
outbox
distributed locks
production deployment wiring
```

---

# 4. Expected accepted Git history

По `003-05` ожидается история:

```text
e4dbc66 feat: add Kaiten connection service
6294a07 feat: add versioned token cipher adapter
e577ed9 feat: add identity onboarding service
f99b2c8 feat: add application service contracts
568a0bb docs: close MVP service data model branch
```

Не считать SHA догмой: зафиксировать фактический `git log`.

Accepted branch base:

```text
002-mvp-service-data-model
```

Accepted base commit expected:

```text
568a0bb docs: close MVP service data model branch
```

---

# 5. Initial Git audit

До staging/commit выполнить:

```powershell
git status --short
git status --ignored --short
git branch --show-current
git branch --list
git log --oneline --decorate --graph -15

git diff --check
git diff --stat
git diff --name-status
```

Ожидаемая branch:

```text
003-application-service-user-onboarding
```

Не использовать:

```text
git reset --hard
git clean -fd
git checkout .
git restore .
```

Не удалять accepted worktree.

---

# 6. Expected uncommitted `003-05` tail

Согласно принятому `003-05` report, после acceptance ожидаются только:

```text
codex/prompts/003_05_full_application_service_acceptance_prompt.md
codex/reports/003_05_full_application_service_acceptance_report.md
tests/integration/test_application_service_acceptance_postgresql.py
```

Текущий `003-06` input prompt:

```text
codex/prompts/003_06_branch_acceptance_git_integration_closeout_prompt.md
```

может быть дополнительным untracked artifact.

Он **не должен** попасть в checkpoint commit `003-05`.

Если присутствуют другие modified/untracked files:

1. классифицировать;
2. определить их происхождение;
3. не удалять автоматически;
4. не включать в commit без доказанной принадлежности ветке `003`.

---

# 7. Branch base verification

Выполнить:

```powershell
git merge-base 002-mvp-service-data-model HEAD
git log --oneline --decorate --graph --all -20
```

Ожидается base:

```text
568a0bb
```

Также проверить ancestry:

```powershell
git merge-base --is-ancestor 002-mvp-service-data-model HEAD
```

Expected:

```text
exit code 0
```

Не выполнять rebase.

Если ветка `003` не основана на accepted `002` closeout:

```text
BLOCKED - BRANCH BASE CONFLICT REQUIRES REVIEW
```

---

# 8. Pre-checkpoint `003-05` quality gate

Перед commit принятого acceptance tail выполнить **последовательно**:

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

Accepted `003-05` reference:

```text
Python 3.12.9
pip check PASS
pytest = 225 passed
pytest -W error = 225 passed
ruff PASS
mypy PASS
Alembic current = 00201_mvp_service_model
Alembic check = no new upgrade operations detected
```

## Важно

Не запускать одновременно:

```text
pytest
pytest -W error
```

против одной `kvc_dev`.

`003-05` доказал, что параллельные полные test processes создают ложные fixture-baseline conflicts в общей development PostgreSQL DB.

Closeout gate всегда выполнять последовательно.

---

# 9. Pre-checkpoint PostgreSQL baseline

Перед acceptance commit безопасно проверить:

```text
KVC_APP_ENV = development
current_database() = kvc_dev
alembic_version = 00201_mvp_service_model
```

Снять row-count baseline:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

Ожидаемый предыдущий baseline:

```text
all = 0
```

Но не удалять legitimate development data, если оно появилось после `003-05`.

Фактический baseline является источником истины.

---

# 10. `003-05` diff audit

Просмотреть:

```text
tests/integration/test_application_service_acceptance_postgresql.py
codex/prompts/003_05_full_application_service_acceptance_prompt.md
codex/reports/003_05_full_application_service_acceptance_report.md
```

Подтвердить:

```text
production code changes = none
test suite is acceptance-only
no schema changes
no dependency changes
no provider mutation code
no live credential value
no real Fernet key
```

`003-05` live probe report может содержать только sanitized PASS metadata.

Не должно быть реального:

```text
Kaiten user id
token
Authorization header
raw provider JSON
```

---

# 11. `003-05` secret/privacy audit

Перед staging проверить commit candidates на:

```text
KVC_KAITEN_API_TOKEN
Authorization:
Bearer
real Fernet key
database password
MAX user IDs
private card/workspace data
raw current-user JSON
```

Допустимы:

```text
environment variable names
synthetic markers
field names
normative security text
runtime-generated ephemeral test keys
```

Не выводить secret-like values в report.

Если найден реальный secret:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

---

# 12. Explicit staging `003-05`

Не использовать:

```text
git add .
```

Явно stage только:

```text
codex/prompts/003_05_full_application_service_acceptance_prompt.md
codex/reports/003_05_full_application_service_acceptance_report.md
tests/integration/test_application_service_acceptance_postgresql.py
```

Не stage текущий `003-06` prompt.

Затем:

```powershell
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
git status --short
```

Просмотреть staged diff.

Повторить staged secret audit.

---

# 13. Acceptance checkpoint commit

Если staged inventory соответствует принятому `003-05`, создать:

```powershell
git commit -m "test: add full application service acceptance"
```

Не amend существующие commits.

Не squash.

Не push.

Не merge.

После:

```powershell
git log -1 --oneline
git status --short
git diff --check
```

Зафиксировать SHA в closeout report.

После commit допустимым dirty artifact должен остаться текущий:

```text
codex/prompts/003_06_branch_acceptance_git_integration_closeout_prompt.md
```

---

# 14. Full branch changed-file inventory

После `003-05` checkpoint сформировать полный inventory ветки относительно **ветки `002`**, не относительно `main`:

```powershell
git diff --stat 002-mvp-service-data-model...HEAD
git diff --name-status 002-mvp-service-data-model...HEAD
```

Классифицировать:

```text
Application contracts
Application services
Integration/security adapters
Configuration
Persistence repository extension
Tests
Prompts
Reports
Environment/example
Unexpected
```

Не считать ожидаемый список исчерпывающим без фактического diff.

---

# 15. Expected production areas

Ожидаемые production changes ветки `003`:

```text
src/kvc_application/
src/kvc_integrations/security/
src/kvc_integrations/kaiten/credential_verifier.py
src/kvc_integrations/system/
src/kvc_config/settings.py
src/kvc_persistence/repositories/max_chats.py
.env.example
```

Tests expected:

```text
tests/unit/test_application_*
tests/unit/test_identity_service.py
tests/unit/test_token_cipher_*
tests/unit/test_kaiten_credential_verifier.py
tests/unit/test_kaiten_connection_service.py
tests/unit/test_clock.py
tests/unit/test_imports.py
tests/unit/test_repository_contracts.py

tests/integration/test_identity_service_postgresql.py
tests/integration/test_kaiten_connection_service_postgresql.py
tests/integration/test_application_service_acceptance_postgresql.py
tests/integration/test_repositories_postgresql.py
```

Prompts/reports:

```text
codex/prompts/003_*.md
codex/reports/003_*.md
```

---

# 16. Unexpected-file gate

Не должны попасть в branch diff:

```text
.env
.venv/
.python312/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
*.pyc
database dump
SQL dump
provider response dump
token/key file
IDE temp file
unrelated future branch work
```

Если useful unrelated work существует:

```text
не удалять
не коммитить в 003
описать separately
```

---

# 17. Full architecture audit

Проверить accepted dependency direction:

```text
transport/future workflows
        ↓
kvc_application
        ↓
application ports + repositories

concrete integrations
        ↑ implement application ports
```

В `src/kvc_application` не должно быть concrete imports:

```text
httpx
cryptography/Fernet
KaitenHttpCredentialVerifier
VersionedFernetTokenCipher
AppSettings
kvc_integrations
MAX SDK/client
```

В report показать результат поиска.

---

# 18. Application contract final audit

Подтвердить наличие frozen contracts:

```text
ResolveMaxIdentityInput
IdentityResolution
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
```

Application errors:

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

Не должно быть hidden product-contract additions.

---

# 19. Secret DTO final audit

Подтвердить `repr=False` / equivalent:

```text
BindKaitenConnectionInput.plaintext_token
KaitenCredentialSnapshot.encrypted_api_token
ActiveKaitenConnectionSecret.plaintext_token
ActiveKaitenConnectionSecret.snapshot
MarkKaitenNeedsReauthInput.snapshot
MarkKaitenNeedsReauthInput.reason
EncryptedToken.ciphertext
```

Не печатать test secret markers.

---

# 20. IdentityService final audit

Подтвердить:

```text
PRIVATE only
same MAX identity -> same user
first message -> ACTIVE user
atomic user + binding + settings
settings default false / 1 / UTC
safe max_chat_id rotation
no identity merge
disabled user remains resolvable
one controlled IntegrityError retry
fresh transaction on retry
race loser -> is_new_user=False
```

Repository extension:

```text
get_private_by_max_user_id_for_update
update_max_chat_id
```

не должен расширяться в generic update framework.

---

# 21. TokenCipher final audit

Подтвердить:

```text
VersionedFernetTokenCipher
authenticated Fernet encryption
one active write version
exact-version decrypt
old-version read support
no MultiFernet trial-decrypt fallback
key mapping private/copied
no automatic key generation
no key material in DB
no key material in Git
```

Critical semantic:

```text
token_encryption_version == crypto key version
```

и не:

```text
credential revision
```

---

# 22. Crypto configuration final audit

External env contract:

```text
KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION
KVC_TOKEN_ENCRYPTION_KEYS
```

Confirm:

```text
key JSON stored as SecretStr or equivalent secret-aware settings value
generic settings startup works without keys
cipher construction fails fast if crypto config missing/invalid
.env.example only safe blank placeholders
.env ignored
```

Не читать `.env` secret values в report.

---

# 23. Kaiten verifier final audit

Подтвердить concrete adapter:

```text
KaitenHttpCredentialVerifier
```

Contract:

```text
injected httpx.AsyncClient
GET {api_base_url.rstrip("/")}/users/current
request-scoped Authorization Bearer
no shared client header mutation
no token in URL/query
```

Mapping:

```text
401/403 -> KaitenAuthenticationFailed
408/429/5xx/timeout/transport -> KaitenTemporarilyUnavailable
other malformed/unexpected contract -> KaitenVerificationFailed
```

Success:

```text
kaiten_user_id = normalized current-user id
workspace_id = None
```

No raw provider response persistence.

---

# 24. Do not repeat live Kaiten probe in closeout

`003-05` already executed and accepted a safe live read-only probe:

```text
GET /users/current
PASS
no mutation
```

`003-06` is Git/branch closeout.

Do **not** make another live Kaiten request merely for repetition.

Closeout should be network-independent.

Use `003-05` report as accepted evidence.

Any new live external call requires explicit new reason and is normally out of scope.

---

# 25. KaitenConnectionService final audit

Подтвердить:

```text
verification outside row locks
encryption outside final write transaction
user preflight
user re-check under lock
canonical user -> connection lock order
one connection per user
first bind ACTIVE
explicit replacement/re-enable ACTIVE
disable idempotent
active secret retrieval
stale-safe mark_needs_reauth
```

No network in:

```text
get_active_connection_secret
mark_needs_reauth
```

---

# 26. Credential snapshot final audit

Frozen snapshot:

```text
connection_id
encrypted_api_token
token_encryption_version
```

Подтвердить отсутствие:

```text
logical credential revision
snapshot hash
fingerprint column
updated_at snapshot semantics
schema field
```

Acceptance already proves:

```text
same crypto version
+
different ciphertext
=
different credential snapshot
```

---

# 27. Lifecycle final audit

Allowed:

```text
missing -> ACTIVE via verified bind
ACTIVE -> ACTIVE via verified replacement
ACTIVE -> NEEDS_REAUTH for matching current snapshot auth failure
ACTIVE -> DISABLED explicit disable
NEEDS_REAUTH -> ACTIVE explicit verified rebind
NEEDS_REAUTH -> DISABLED explicit disable
DISABLED -> ACTIVE explicit verified rebind
```

Stale snapshot:

```text
no-op
```

Disabled snapshot reauth mark:

```text
remains DISABLED
```

No unapproved status exists.

---

# 28. Repository transaction final audit

Inspect:

```text
UserRepository
MaxChatRepository
KaitenConnectionRepository
NotificationSettingsRepository
```

and application services.

Confirm:

```text
repository commit() = none
repository rollback() = none
application services own transaction scopes
FOR UPDATE paths present
lock ordering coherent
```

No HTTP calls in repositories.

No encryption in repositories.

---

# 29. Persistence/schema audit

No `003` schema work was accepted.

Run:

```powershell
git diff --check 002-mvp-service-data-model...HEAD -- src/kvc_persistence/models.py src/kvc_persistence/migrations
git diff --name-status 002-mvp-service-data-model...HEAD -- src/kvc_persistence/models.py src/kvc_persistence/migrations
```

Expected:

```text
no model/migration diff
```

Only accepted repository extension should appear under persistence.

Alembic:

```text
head/current = 00201_mvp_service_model
```

No `003` migration.

---

# 30. Dependency audit

Check:

```powershell
git diff 002-mvp-service-data-model...HEAD -- pyproject.toml
```

`003-03` confirmed `cryptography` was already a direct dependency.

Expected branch `003` dependency change:

```text
none
```

Do not upgrade packages on closeout.

---

# 31. `.env.example` final audit

Review branch diff.

Allowed additions:

```text
KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION=
KVC_TOKEN_ENCRYPTION_KEYS=
```

No:

```text
real Fernet key
real token
old obsolete single-key production contract
```

Do not modify real `.env`.

---

# 32. Full branch secret/hygiene audit

Audit all branch-added/modified files relative to `002`.

Markers minimum:

```text
Authorization
Bearer
KVC_KAITEN_API_TOKEN
KVC_TOKEN_ENCRYPTION_KEYS
password
PRIVATE KEY
Fernet
plaintext_token
encrypted_api_token
```

Classify matches:

```text
safe env-name reference
synthetic test marker
secret-aware config field
normative security text
real secret
```

Do not print real secret values.

Real secret:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

---

# 33. Test-data privacy audit

Confirm tests contain only:

```text
synthetic UUIDs
synthetic MAX IDs
synthetic tokens
ephemeral Fernet keys
synthetic provider payloads
synthetic api_base_url values
```

No real:

```text
MAX identity
Kaiten user ID
workspace/card data
credential
DB password
```

Live `003-05` report deliberately does not record normalized real Kaiten user ID.

---

# 34. Final PostgreSQL state audit

Read-only verify:

```text
KVC_APP_ENV = development
database = kvc_dev
alembic_version = 00201_mvp_service_model
```

Record business-table counts.

Expected from `003-05`:

```text
all seven business tables = 0
```

but use actual baseline as truth.

Do not perform broad cleanup.

Do not run downgrade.

Do not run DDL.

---

# 35. Acceptance-suite operational note

Preserve the discovered test-operation constraint in closeout report:

```text
Full PostgreSQL-backed pytest invocations must run sequentially
when they share the same kvc_dev database.
```

Reason:

```text
parallel independent full pytest processes can interfere with shared fixture baseline accounting
```

This is test-infrastructure operational guidance, not an application defect.

Do not add a package/dependency to solve this in closeout.

---

# 36. Pre-closeout full gate

After `003-05` checkpoint and full branch audit, run again **sequentially**:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip check

.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error

.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src

.venv\Scripts\python.exe -m alembic -c alembic.ini heads
.venv\Scripts\python.exe -m alembic -c alembic.ini history
.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check

git diff --check 002-mvp-service-data-model...HEAD
```

Expected:

```text
pytest >= 225 passed
pytest -W error >= 225 passed
Ruff PASS
mypy PASS
pip check PASS
Alembic head/current = 00201_mvp_service_model
Alembic check = no drift
```

No new live Kaiten call.

---

# 37. Production correction policy

Expected closeout production corrections:

```text
none
```

If audit finds:

```text
formatting defect
obvious docs inconsistency
test cleanup issue
```

minimal closeout correction is allowed.

If it finds a functional service/security/concurrency defect:

```text
do not bury it in docs commit
```

Classify:

```text
implementation bug
or
new architecture decision
```

If functional defect requires production correction, run affected acceptance again.

If architectural decision required:

```text
BLOCKED - BRANCH CLOSEOUT CORRECTION REQUIRED
```

---

# 38. Create closeout report before final docs commit

Create:

```text
codex/reports/003_06_branch_acceptance_git_integration_closeout_report.md
```

Report must be complete before final documentation commit.

Current prompt:

```text
codex/prompts/003_06_branch_acceptance_git_integration_closeout_prompt.md
```

and report belong together in final closeout documentation commit.

---

# 39. Closeout report structure

Report must contain at minimum:

1. Executive summary.
2. Initial branch/worktree state.
3. Branch base verification.
4. Pre-checkpoint `003-05` gate.
5. `003-05` PostgreSQL baseline.
6. `003-05` diff/secret audit.
7. Exact staged `003-05` inventory.
8. `003-05` checkpoint SHA/message.
9. Post-checkpoint worktree state.
10. Full branch changed-file inventory.
11. Unexpected-file review.
12. Application dependency architecture audit.
13. Application contract inventory.
14. Secret DTO audit.
15. IdentityService final audit.
16. MAX repository extension audit.
17. TokenCipher final audit.
18. Crypto configuration audit.
19. Kaiten verifier final audit.
20. Accepted live-probe evidence from `003-05`.
21. Explicit statement that closeout made no live call.
22. UtcClock final audit.
23. KaitenConnectionService final audit.
24. Credential snapshot final audit.
25. Lifecycle/status audit.
26. Transaction/lock-order audit.
27. Persistence/schema audit.
28. Dependency audit.
29. `.env.example` audit.
30. Secret/hygiene audit.
31. Test-data privacy audit.
32. PostgreSQL final-state verification.
33. Sequential-test operational note.
34. Pre-closeout full gate.
35. Production corrections, if any.
36. `003-05` acceptance checkpoint commit.
37. Final documentation commit plan.
38. Final documentation staged audit.
39. Final documentation commit SHA/message.
40. Final branch history.
41. Final diff vs `002-mvp-service-data-model`.
42. Final worktree clean state.
43. Final ignored environment state.
44. Final post-commit quality gate.
45. Database final state.
46. Explicit deferred work.
47. Accepted next-branch base commit.
48. Final branch status.

---

# 40. Final documentation staging

После report creation stage explicitly:

```text
codex/prompts/003_06_branch_acceptance_git_integration_closeout_prompt.md
codex/reports/003_06_branch_acceptance_git_integration_closeout_report.md
```

Если в ходе closeout был сделан strictly necessary documentation-only correction в уже существующем `003` artifact, stage его здесь и объяснить.

Не использовать:

```text
git add .
```

Then:

```powershell
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
```

Review staged diff.

Repeat staged secret audit.

---

# 41. Final documentation commit

Create:

```powershell
git commit -m "docs: close application service onboarding branch"
```

Do not amend previous acceptance commit.

Do not merge.

Do not push.

After commit:

```powershell
git log -1 --oneline
git status --short
```

Expected:

```text
git status --short
<no output>
```

---

# 42. Final branch history

Get:

```powershell
git log --oneline --decorate --graph 002-mvp-service-data-model..HEAD
```

Expected logical sequence should include at least:

```text
docs: close application service onboarding branch
test: add full application service acceptance
feat: add Kaiten connection service
feat: add versioned token cipher adapter
feat: add identity onboarding service
feat: add application service contracts
```

Exact hashes recorded in report.

Do not rewrite history merely to improve aesthetics.

---

# 43. Final diff vs accepted branch `002`

Use:

```powershell
git diff --check 002-mvp-service-data-model...HEAD
git diff --stat 002-mvp-service-data-model...HEAD
git diff --name-status 002-mvp-service-data-model...HEAD
```

Do **not** use `main` as the primary comparison baseline for branch `003`, because `003` was explicitly based on accepted branch `002`.

Report may optionally show:

```text
main...HEAD
```

for information only, but closeout correctness is judged against:

```text
002-mvp-service-data-model
```

Confirm no unrelated future work.

---

# 44. Worktree clean gate

After all commits:

```powershell
git status --short
```

Expected:

```text
<no output>
```

Ignored local artifacts may remain:

```text
.env
.venv/
.python312/
coverage/cache artifacts
```

Check:

```powershell
git status --ignored --short .env .venv .python312
```

Expected ignored markers only.

Do not require deletion of ignored environments.

---

# 45. Final post-commit quality gate

После final documentation commit повторить critical gate **последовательно**:

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

git status --short
git diff --check 002-mvp-service-data-model...HEAD
```

Commit process must not alter gate result.

---

# 46. Final database verification

После post-commit gate:

```text
database = kvc_dev
alembic_version = 00201_mvp_service_model
```

Record all seven business row counts.

Expected to equal pre-closeout baseline.

Do not clean legitimate development data.

No DDL.

No live external provider call.

---

# 47. No remote integration

`003-06` closes the local branch.

Do not:

```text
git push
git merge main
git merge 002
git rebase
force push
open PR through remote tooling
```

Remote integration is a separate user action/stage if needed.

Remain on:

```text
003-application-service-user-onboarding
```

at end.

---

# 48. Accepted base for next branch

Report final HEAD SHA after:

```text
docs: close application service onboarding branch
```

as:

```text
accepted next-branch base commit
```

Do not create branch `004` automatically.

Do not choose next feature scope unless already explicitly fixed elsewhere.

State only:

```text
new functional work must branch from accepted final HEAD of 003
```

---

# 49. Explicit deferred work

Closeout report must clearly distinguish future features from unfinished `003` work.

Deferred:

```text
MAX transport/bot integration
MAX polling/webhook strategy
user-facing onboarding conversation
Kaiten card listing
column/card resolution
comments
deadline set/change/remove
attachments/photos
card summary
GigaChat intent processing
STT/voice input
dialog session orchestration
PendingCommand workflow
notification polling/delivery
disabled-user notification filtering
future card mutation explicit-command policy
commercial/access layer
```

These are future branches.

They do not block closure of application-service branch `003`.

---

# 50. What is forbidden

On `003-06` do not:

- add new business feature;
- add MAX transport;
- add card commands;
- add notification worker;
- add new DB table/column;
- create new Alembic revision;
- change frozen application contracts;
- change crypto scheme;
- make another live Kaiten request without a new explicit reason;
- expose `.env` values;
- add dependency;
- broad-clean PostgreSQL;
- use destructive Git commands;
- merge/push/rebase;
- open next branch.

---

# 51. Acceptance criteria — branch integrity

Branch `003` is accepted only if:

- current branch is `003-application-service-user-onboarding`;
- base is accepted `002-mvp-service-data-model`;
- no unexpected source/future work in branch diff;
- all accepted `003` artifacts are committed;
- `003-05` acceptance suite is committed separately;
- `003-06` prompt/report are committed in final docs commit;
- final branch history is coherent;
- final worktree is clean;
- no remote operation performed.

---

# 52. Acceptance criteria — application architecture

Required:

- application contracts unchanged from frozen spec;
- application layer has no concrete integration/config imports;
- `IdentityService` contract accepted;
- `KaitenConnectionService` contract accepted;
- repositories do not own commit/rollback;
- provider verification occurs outside DB locks;
- canonical locking contract retained;
- no local Kaiten content cache;
- no unexpected provider/network behavior.

---

# 53. Acceptance criteria — identity/onboarding

Required:

- PRIVATE MAX only;
- automatic first-message user creation;
- ACTIVE user default;
- one primary binding;
- settings eager creation false/1/UTC;
- idempotent repeated resolution;
- safe chat rotation;
- no identity merge;
- disabled identity resolves;
- controlled concurrency retry;
- integration acceptance passes.

---

# 54. Acceptance criteria — security/crypto

Required:

- plaintext token never persisted;
- public DTOs contain no token/ciphertext;
- secret DTO repr protected;
- Fernet authenticated encryption;
- exact version -> exact key;
- active write key version;
- old key read support;
- no trial-decrypt fallback;
- no real keys in Git;
- key config external/secret-aware;
- `token_encryption_version` is only crypto version;
- stale snapshot compares ciphertext as well as version;
- secret audit PASS.

---

# 55. Acceptance criteria — Kaiten lifecycle

Required:

- read-only credential verifier accepted;
- accepted `003-05` live probe PASS;
- no closeout live probe required;
- first bind ACTIVE;
- replacement/re-enable ACTIVE;
- failure leaves old state unchanged;
- disable idempotent;
- active secret retrieval correct;
- current auth failure -> NEEDS_REAUTH;
- stale auth failure -> no-op;
- same crypto version different ciphertext remains stale-safe;
- no schema changes.

---

# 56. Acceptance criteria — infrastructure

Required:

- Python 3.12.9 baseline;
- full pytest PASS;
- `pytest -W error` PASS;
- PostgreSQL-backed full suites run sequentially;
- Ruff PASS;
- mypy PASS;
- pip check PASS;
- Alembic head/current `00201_mvp_service_model`;
- Alembic check no drift;
- no dependency diff;
- no model/migration diff;
- final DB counts equal starting baseline;
- `git diff --check 002...HEAD` PASS.

---

# 57. Final status

If all closeout criteria pass:

```text
BRANCH 003 ACCEPTED AND CLOSED - READY FOR NEXT BRANCH
```

If unexpected/unrelated Git content or secret exists:

```text
BLOCKED - GIT HYGIENE CORRECTION REQUIRED
```

If final quality/database gate fails:

```text
BLOCKED - BRANCH CLOSEOUT CORRECTION REQUIRED
```

If branch base does not derive from accepted `002`:

```text
BLOCKED - BRANCH BASE CONFLICT REQUIRES REVIEW
```

If architecture/application acceptance no longer matches frozen contract:

```text
BLOCKED - FROZEN CONTRACT CONFLICT
```

---

## Главное правило

`003-06` не добавляет функциональность.

Он должен завершить:

```text
accepted application service implementation
+
accepted cross-service tests
+
logical Git history
+
full branch diff audit
+
secret/schema/dependency hygiene
+
final sequential project gate
+
clean worktree
+
closeout documentation
```

И оставить один однозначный результат:

```text
финальный HEAD ветки 003
=
принятая база для следующей функциональной ветки
```
