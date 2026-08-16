# 003-00 — Application service layer, user identity onboarding and credential lifecycle audit

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Предыдущая ветка:

```text
002 — MVP service data model
```

закрыта и принята.

Ключевой итог ветки `002`:

```text
PostgreSQL
    ↓
SQLAlchemy ORM
    ↓
Alembic
    ↓
async repositories / row locking / transaction-safe query primitives
```

Закрывающий отчёт:

```text
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

Новая ветка:

```text
003 — Application service layer and user onboarding
```

На этом этапе требуется **аудит**, а не реализация.

---

# 1. Главная цель

Спроектировать application/service layer, который будет расположен **над persistence repositories** и **под внешними transport/integration adapters**.

Необходимо определить окончательные контракты для:

```text
MAX identity -> KVC user binding
KVC user lifecycle
Kaiten connection lifecycle
Kaiten token encryption/decryption boundary
default notification settings creation
application transaction orchestration
application service interfaces
application DTO/input contracts
error contracts
layer dependencies
```

После `003-00` должно быть понятно:

1. какие application services нужны MVP;
2. какие операции являются атомарными;
3. кто открывает/закрывает DB transaction;
4. где проходит граница plaintext Kaiten token;
5. как создаётся KVC user;
6. как MAX identity привязывается к KVC user;
7. как создаётся/обновляется Kaiten connection;
8. как обрабатывается invalid/revoked Kaiten token;
9. какие действия можно реализовать до появления реального MAX/Kaiten adapter;
10. как разбить ветку `003` на конкретные последующие implementation stages.

---

# 2. Нормативная база

Перед выводами обязательно изучи:

```text
codex/reports/002_00a_mvp_service_data_model_final_specification.md
codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
codex/reports/002_01_mvp_service_data_model_implementation_report.md
codex/reports/002_02_live_postgresql_persistence_acceptance_report.md
codex/reports/002_03_repository_query_contracts_implementation_report.md
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

Также изучи:

```text
src/
tests/
pyproject.toml
```

Особенно:

```text
src/kvc_persistence/models.py
src/kvc_persistence/repositories/
src/kvc_persistence/session.py
src/kvc_persistence/engine.py
```

Если в репозитории есть MVP/architecture specification — использовать её как primary product source.

Не выводить новые product requirements без основания.

---

# 3. Frozen persistence contract

Ветка `003` не должна пересматривать уже принятую schema.

Существуют ровно семь business tables:

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

Не предлагать новую migration, если audit не обнаружит объективный blocker.

---

# 4. Frozen repository contract

Из `002-03` уже доступны:

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

Repository layer:

- работает через `AsyncSession`;
- не вызывает `commit()`;
- не вызывает `rollback()`;
- предоставляет `FOR UPDATE`;
- enforce'ит PendingCommand ownership invariant;
- предоставляет atomic notification reservation.

Application layer должен **использовать**, а не дублировать эти primitives.

---

# 5. Слоистая архитектура — определить окончательно

Нужно проверить и зафиксировать dependency direction.

Базовый кандидат:

```text
transport layer
(MAX bot / future HTTP/API)
        ↓
application layer
        ↓
domain/application contracts
        ↓
persistence repositories
        ↓
SQLAlchemy/PostgreSQL
```

External integrations:

```text
Kaiten API
MAX API
GigaChat
SaluteSpeech
```

должны быть adapters, а не зависимостями persistence layer.

Определи:

- какие зависимости разрешены;
- какие запрещены;
- где должны жить protocols/interfaces;
- где должны жить DTO;
- где должны жить integration-specific exceptions;
- может ли application layer импортировать SQLAlchemy ORM models напрямую или должен работать через repository-returned entities.

Не создавать абстракции ради абстракций.

---

# 6. Transaction orchestration

Это центральная задача аудита.

Repository methods не владеют commit/rollback.

Нужно определить application transaction pattern.

Предпочтительный кандидат:

```python
async with session.begin():
    ...
```

или существующий проектный equivalent.

Для каждой application operation определить:

```text
transaction start
repository calls
external calls before/inside/after transaction
flush points
commit point
failure rollback behavior
```

Особенно важно не держать PostgreSQL row locks во время длительных network calls без необходимости.

---

# 7. User identity model

Frozen schema:

```text
users
max_chats
```

Нужно определить фактическую MVP semantics:

```text
MAX user/chat identity -> one KVC user
```

MAX scope:

```text
PRIVATE 1:1 only
```

Аудит должен ответить:

1. Что является входным identity key:
   - `max_user_id`;
   - `max_chat_id`;
   - их пара?
2. Как определить существующего KVC user.
3. Когда создаётся новый `users` row.
4. Когда создаётся `max_chats` binding.
5. Что делать, если:
   - `max_user_id` известен, но `max_chat_id` изменился;
   - `max_chat_id` уже привязан;
   - найден conflicting binding;
   - user.status = `DISABLED`.
6. Нужно ли MVP автоматически создавать user при первом входящем private MAX message.
7. Нужна ли отдельная explicit onboarding command или достаточно lazy creation.

Дай recommendation с последствиями.

---

# 8. MAX binding transaction

Спроектировать атомарный application flow, например:

```text
resolve/bind MAX identity
```

Candidate:

```text
BEGIN
  lookup max_chat_id
  lookup private max_user_id
  resolve existing user / create user
  create/update MAX binding
  ensure default notification_settings
COMMIT
```

Но audit должен проверить race conditions и предложить правильный порядок locking/repository calls.

Учитывать DB constraints:

```text
uq_max_chats_max_chat_id
uq_max_chats_max_user_id_private
uq_max_chats_user_primary
```

Не проектировать group chat.

---

# 9. Default `notification_settings`

Нужно определить:

- создаётся ли `notification_settings` вместе с onboarding;
- либо lazy при первом `/notify`;
- кто вызывает `NotificationSettingsRepository.get_or_create_for_user()`.

Recommendation должна учитывать:

```text
enabled = false
due_soon_days = 1
timezone = UTC
```

Нельзя предполагать timezone пользователя без явного сигнала.

---

# 10. Kaiten connection lifecycle

Frozen table:

```text
kaiten_connections
```

MVP cardinality:

```text
1 user -> 1 Kaiten connection
```

Statuses:

```text
ACTIVE
DISABLED
NEEDS_REAUTH
```

Нужно определить application operations:

```text
bind_kaiten_connection
replace_kaiten_token
disable_kaiten_connection
mark_needs_reauth
mark_verified
get_active_connection
```

или минимально необходимый эквивалент.

Не реализовывать HTTP client на этом этапе аудита.

---

# 11. Plaintext Kaiten token boundary

Это security-critical architectural boundary.

Frozen persistence stores:

```text
encrypted_api_token BYTEA
token_encryption_version SMALLINT
```

Plaintext token нельзя сохранять.

Аудит должен однозначно определить жизненный цикл:

```text
plaintext token enters application boundary
        ↓
optional remote verification against Kaiten
        ↓
encryption service
        ↓
ciphertext
        ↓
repository
        ↓
PostgreSQL
```

И обратный путь для API call:

```text
repository ciphertext
        ↓
decryption service
        ↓
short-lived plaintext in memory
        ↓
Kaiten adapter call
        ↓
plaintext discarded
```

Определи, какие слои имеют право видеть plaintext.

---

# 12. Encryption service contract

Не реализовывать криптографию в `003-00`, но определить interface.

Пример кандидата:

```text
TokenCipher
  encrypt(plaintext: str) -> EncryptedToken
  decrypt(ciphertext: bytes, version: int) -> str
```

Нужно решить:

- возвращать ли только bytes;
- нужен ли explicit result с `version`;
- кто задаёт `token_encryption_version`;
- как будет поддерживаться future key rotation;
- где берётся master/key material;
- какие error types нужны;
- что запрещено логировать.

Не хранить encryption key в PostgreSQL.

---

# 13. Выбор криптографического подхода

Не изобретай собственную криптографию.

Аудит должен проверить current project dependencies и определить, какой vetted library/primitive разумно использовать.

Если для выбора конкретной библиотеки/algorithm требуется актуальная внешняя техническая проверка — используй только официальную документацию библиотек/стандартов и явно отдели этот research от repository-derived conclusions.

Предпочтение:

- authenticated encryption;
- стандартная поддерживаемая библиотека;
- key/version rotation;
- минимальный custom cryptographic code.

Не реализовывать crypto в audit stage.

---

# 14. Token verification ordering

Нужно решить важный transaction/network вопрос.

При привязке нового Kaiten token возможны варианты:

## A

```text
verify plaintext token against Kaiten
encrypt
DB transaction persist
```

## B

```text
encrypt
DB transaction persist unverified
remote verify
update status
```

## C

другой безопасный flow.

Рекомендация должна учитывать:

- нельзя долго держать DB transaction на network call;
- нельзя сохранять заведомо invalid token как `ACTIVE`;
- plaintext должен существовать минимально;
- external API may fail transiently;
- distinction invalid credentials vs temporary Kaiten outage.

---

# 15. Kaiten connection status semantics

Формализовать:

## `ACTIVE`

Когда connection можно использовать.

## `DISABLED`

Кем/зачем выставляется.

## `NEEDS_REAUTH`

Когда:

```text
401/invalid/revoked token
```

и чем отличается от:

```text
Kaiten 5xx
network timeout
rate limit
```

Не использовать `NEEDS_REAUTH` для любого transient external failure.

---

# 16. Application error taxonomy

Определить минимальный набор application errors.

Возможные категории:

```text
UserDisabled
IdentityConflict
KaitenConnectionMissing
KaitenAuthenticationFailed
KaitenTemporarilyUnavailable
CredentialEncryptionFailed
CredentialDecryptionFailed
PersistenceConflict
```

Не плодить hierarchy без необходимости.

Нужно определить:

- какие ошибки transport layer может переводить в user-facing response;
- какие считаются retryable;
- какие нельзя логировать с payload.

---

# 17. Application service inventory

Сформировать рекомендуемый минимальный набор services.

Например:

```text
IdentityService
KaitenConnectionService
```

или другой более удачный decomposition.

Не создавать сервис на каждую таблицу.

Каждый service должен соответствовать application use-cases, а не CRUD.

Для каждого указать:

```text
responsibility
inputs
outputs
repositories used
external ports used
transaction boundary
errors
```

---

# 18. Ports / interfaces

Определи, какие external interfaces уже нужны на application boundary, даже если adapter будет реализован позже.

Кандидаты:

```text
KaitenCredentialVerifier
TokenCipher
```

Возможно:

```text
Clock
```

только если это реально улучшает тестируемость status/timestamp logic.

Не вводить MAX port без use-case, если transport integration будет отдельной веткой.

---

# 19. DTO / command inputs

Определи минимальные application input structures.

Например:

```text
ResolveMaxIdentityInput
BindKaitenConnectionInput
```

Нужно решить:

- dataclass;
- frozen dataclass;
- pydantic;
- primitive parameters.

Application DTO не должны быть:

```text
HTTP request schemas
MAX SDK DTO
SQLAlchemy models
```

без явной причины.

---

# 20. User onboarding flow

Аудит должен дать sequence diagram / пошаговый flow для первого пользователя.

Минимум:

```text
incoming MAX private identity
        ↓
resolve/create KVC user
        ↓
bind primary MAX chat
        ↓
ensure notification settings
        ↓
user exists but Kaiten not connected
        ↓
application signals onboarding state
```

Не реализовывать actual MAX response text.

---

# 21. Kaiten onboarding flow

Отдельно:

```text
user provides Kaiten token
        ↓
verify
        ↓
encrypt
        ↓
persist connection
        ↓
mark ACTIVE/last_verified_at
```

Обязательно указать transaction/network boundaries.

---

# 22. Re-auth flow

Определить flow:

```text
Kaiten API returns authentication failure
        ↓
mark connection NEEDS_REAUTH
        ↓
subsequent command does not attempt protected operation blindly
        ↓
user supplies new token
        ↓
verify
        ↓
replace encrypted token
        ↓
ACTIVE
```

Не реализовывать actual command handler.

---

# 23. Disabled user behavior

Frozen:

```text
users.status = ACTIVE | DISABLED
```

Определи:

- application guard location;
- какие operations запрещены `DISABLED` user;
- можно ли identity lookup вернуть disabled user;
- должен ли transport layer отвечать generic disabled-state message;
- можно ли background worker обрабатывать disabled user.

Не реализовывать user deletion.

---

# 24. Transaction + external call matrix

Сделай отдельную таблицу:

```text
use case
DB transaction
row locks
external call
order
failure behavior
```

Минимум для:

```text
resolve/create MAX user
bind Kaiten credential
replace Kaiten credential
mark NEEDS_REAUTH
disable user
```

---

# 25. Concurrency analysis

Проверить race cases:

```text
two first MAX messages arrive concurrently
two token-binding attempts concurrently
token rebind while command processing reads connection
user disabled while connection update runs
```

Для каждого указать:

- repository locks;
- DB constraints;
- application behavior;
- acceptable loser/winner semantics.

Не вводить distributed lock, если PostgreSQL row locking достаточно.

---

# 26. Session/transaction API

Определить, как application service получает `AsyncSession`.

Возможные подходы:

```text
session passed into service method
service constructed with session
session factory injected into orchestration layer
```

Не создавать UnitOfWork автоматически.

Recommendation должна соответствовать существующему session foundation и сохранять:

```text
repository does not own transaction
application orchestration owns transaction
```

---

# 27. Logging and secret redaction contract

Определить, что разрешено логировать.

Можно:

```text
user_id
connection_id
status transitions
safe error type
external HTTP status class
```

Нельзя:

```text
plaintext Kaiten token
encrypted token bytes
encryption key
Authorization header
full secret-bearing URL
.env values
```

Должна существовать явная redaction policy.

---

# 28. Testing strategy for future implementation

Сформировать test matrix для последующих задач.

Минимум:

## Unit

```text
service orchestration
error mapping
token cipher interface mocks
verification port mocks
disabled user guard
identity conflict
```

## PostgreSQL integration

```text
concurrent onboarding
atomic MAX binding
Kaiten connection replace
row-lock behavior
rollback on application error
```

## Security

```text
plaintext never persisted
plaintext absent from repr/logs
ciphertext bytes persisted
wrong key/version failure
```

Не реализовывать tests в audit stage.

---

# 29. Branch decomposition

На основе аудита предложить точный plan ветки `003`.

Ожидаемый формат:

```text
003-00 audit
003-00a final specification, если нужны решения пользователя
003-01 ...
003-02 ...
...
003-closeout
```

Не делать слишком мелкую декомпозицию.

Каждый этап должен иметь один ясный acceptance target.

---

# 30. Decisions requiring user approval

Вынести отдельным разделом только реальные архитектурные решения.

Возможные кандидаты:

1. auto-create KVC user on first MAX private message или explicit onboarding;
2. `notification_settings` eager или lazy creation;
3. token verification-before-persist policy;
4. concrete crypto/key-management strategy;
5. behavior when token verification is temporarily unavailable;
6. replacement semantics для existing Kaiten connection.

Для каждого:

```text
Option A
Option B
Recommendation
Consequences
```

Не выносить технические мелочи, которые Codex может решить самостоятельно.

---

# 31. Что нельзя делать на `003-00`

Запрещено:

- менять production code;
- менять tests;
- создавать migration;
- менять DB schema;
- вызывать live Kaiten;
- вызывать MAX;
- реализовывать encryption;
- добавлять dependencies;
- создавать application services;
- создавать DTO;
- создавать ports;
- менять `.env`;
- выполнять Git commit;
- переключать architecture без user decision.

Это audit-only stage.

---

# 32. Repository/database safety

Допустимо read-only проверить:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

Не выполнять:

```text
upgrade
downgrade
DDL
DML
```

на этом audit stage.

---

# 33. Git baseline

Перед аудитом:

```powershell
git branch --show-current
git status --short
git log --oneline --decorate -5
git diff --check
```

Ожидается чистая закрытая ветка:

```text
002-mvp-service-data-model
```

Не создавать ветку `003` автоматически, если prompt выполняется до explicit Git branch-opening convention проекта.

В отчёте предложить рекомендуемое имя новой ветки.

---

# 34. Рекомендуемое имя ветки

Предложить:

```text
003-application-service-user-onboarding
```

или более точное имя, если аудит покажет лучший scope.

Не создавать branch автоматически на `003-00`, если это не принято текущим workflow.

---

# 35. Quality gate

Так как production code не меняется, выполнить baseline gate:

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

Не исправлять unrelated issues автоматически.

---

# 36. Итоговый report

Создай:

```text
codex/reports/003_00_application_service_user_onboarding_audit_report.md
```

Report должен содержать минимум:

1. Executive summary.
2. Source requirements.
3. Current branch/runtime/persistence baseline.
4. Existing layer inventory.
5. Proposed dependency direction.
6. Application transaction ownership.
7. User/MAX identity semantics.
8. MAX onboarding transaction.
9. Notification settings creation policy.
10. Kaiten connection lifecycle.
11. Plaintext token boundary.
12. Encryption service contract.
13. Crypto/key-management options.
14. Token verification ordering.
15. Kaiten status semantics.
16. Application error taxonomy.
17. Application service inventory.
18. Ports/interfaces.
19. DTO/input contracts.
20. First-user onboarding flow.
21. Kaiten onboarding flow.
22. Re-auth flow.
23. Disabled-user behavior.
24. Transaction/external-call matrix.
25. Concurrency analysis.
26. Session ownership recommendation.
27. Logging/redaction contract.
28. Future testing strategy.
29. Decisions requiring user approval.
30. Recommended branch plan.
31. Recommended branch name.
32. Explicit out-of-scope.
33. Quality gate.
34. Changed files.
35. Final status.

---

# 37. Changed files

Ожидается:

```text
Production code:
none

Tests:
none

Alembic:
none

Configuration:
none

Report:
codex/reports/003_00_application_service_user_onboarding_audit_report.md
```

Если prompt itself уже существует в repository:

```text
codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
```

не считать его production change.

---

# 38. Final status

Если архитектура application layer определена, но есть решения пользователя:

```text
READY WITH DECISIONS REQUIRED
```

Если все существенные решения уже однозначно следуют из accepted architecture:

```text
READY FOR 003-01
```

Если persistence foundation реально недостаточен:

```text
BLOCKED - PERSISTENCE CONTRACT GAP
```

Не начинать implementation на `003-00`.

---

## Главное правило

Ветка `002` завершила вопрос:

```text
как безопасно хранить и извлекать состояние
```

Ветка `003` должна ответить:

```text
кто и в какой транзакции использует это состояние
```

`003-00` должен спроектировать application orchestration и onboarding boundary так, чтобы последующие MAX/Kaiten integrations подключались как внешние adapters, а не проникали в persistence layer.
