# 003-00a — Final application service and user onboarding specification

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Функциональный этап:

```text
003 — Application service layer and user onboarding
```

Предыдущий этап:

```text
003-00 — Application service layer, user identity onboarding and credential lifecycle audit
```

завершён отчётом:

```text
codex/reports/003_00_application_service_user_onboarding_audit_report.md
```

Аудит рассмотрен пользователем, архитектурные решения приняты.

На этом этапе необходимо **зафиксировать окончательную спецификацию application/service layer для user onboarding и Kaiten credential lifecycle**.

Это **спецификационный этап**, а не реализация.

Не создавать application services, DTO, ports, adapters, tests, migrations или новую production-функциональность.
К реализации `003-01` переходить только после отдельного подтверждения пользователя.

---

# 1. Главная цель

Подготовить самодостаточный frozen contract ветки `003`, достаточный для последующей непосредственной реализации:

```text
MAX private identity
    ↓
IdentityService
    ↓
KVC user + MAX binding + notification defaults

user explicit command
    ↓
KaitenConnectionService
    ↓
credential verification
    ↓
token encryption
    ↓
verified encrypted persistence
```

Итоговая спецификация должна однозначно определить:

1. application-layer dependency boundaries;
2. состав application services;
3. DTO contracts;
4. application ports;
5. error taxonomy;
6. MAX identity resolution/onboarding semantics;
7. MAX chat rotation/rebinding semantics;
8. KVC user lifecycle guards;
9. default notification settings creation;
10. Kaiten connection lifecycle;
11. credential verification-before-persist policy;
12. plaintext token boundary;
13. encryption/key-version contract;
14. transaction ownership;
15. external-call/transaction ordering;
16. concurrency and idempotency semantics;
17. stale-credential protection для `mark_needs_reauth`;
18. disabled-user guards;
19. dependency-injection/composition boundary;
20. точный scope последующих implementation stages.

После `003-00a` у `003-01...003-04` не должно оставаться архитектурных развилок по этому слою.

---

# 2. Обязательная нормативная база

В первую очередь изучи:

```text
codex/reports/003_00_application_service_user_onboarding_audit_report.md
```

Также обязательно изучи принятый persistence baseline ветки `002`:

```text
codex/reports/002_00a_mvp_service_data_model_final_specification.md
codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
codex/reports/002_01_mvp_service_data_model_implementation_report.md
codex/reports/002_02_live_postgresql_persistence_acceptance_report.md
codex/reports/002_03_repository_query_contracts_implementation_report.md
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

Проверь также:

```text
docs/specifications/
docs/architecture/
AGENTS.md
README.md
pyproject.toml
src/
tests/
```

Особенно:

```text
src/kvc_persistence/models.py
src/kvc_persistence/repositories/
src/kvc_persistence/session.py
src/kvc_persistence/engine.py
src/kvc_application/
src/kvc_domain/
src/kvc_integrations/
```

Не проектируй persistence layer заново.

Если документы отличаются по приоритету, использовать следующий принцип:

```text
accepted live/final corrections
    >
final specifications
    >
implementation/acceptance reports
    >
audit rationale
```

Если найдено реальное противоречие, зафиксируй его, но не расширяй scope самостоятельно.

---

# 3. Frozen persistence baseline — не пересматривать

Ветка `002` зафиксировала семь business tables:

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

Ключевые persistence invariants:

```text
MAX scope = PRIVATE only
one primary MAX private binding per KVC user
one Kaiten connection per KVC user
repositories use AsyncSession
repositories do not commit
repositories do not rollback
application/service layer owns transactions
Kaiten content is not persistently copied into KVC DB
plaintext Kaiten token is never persisted
kaiten_connections stores:
    encrypted_api_token BYTEA
    token_encryption_version
notification_settings defaults:
    enabled = false
    due_soon_days = 1
    timezone = UTC
```

Не менять schema и не создавать Alembic migration на `003-00a`.

---

# 4. Принятые решения пользователя

Все решения ниже считаются **утверждёнными** и не должны повторно выноситься на выбор.

## Decision 1 — Automatic first-message onboarding

При первом входящем сообщении в приватном MAX-чате KVC:

```text
автоматически создаёт KVC user,
если MAX identity ещё не известна.
```

Отдельный registration/onboarding screen в MVP не требуется.

---

## Decision 2 — Eager notification settings

При создании нового KVC user в той же транзакции создаётся:

```text
notification_settings
```

с уже frozen defaults:

```text
enabled = false
due_soon_days = 1
timezone = UTC
```

Lazy creation не использовать как основной onboarding path.

---

## Decision 3 — Verify Kaiten credential before persistence

Новый или заменяемый Kaiten credential необходимо:

```text
verify
    ↓
encrypt
    ↓
persist as ACTIVE
```

Невалидный token:

```text
не сохраняется
```

Непроверенный из-за transient outage token:

```text
не сохраняется как ACTIVE
```

Не вводить новый persistence status `UNVERIFIED`.

---

## Decision 4 — TokenCipher + versioned external keys

Application layer зависит от абстракции:

```text
TokenCipher
```

Concrete crypto adapter:

```text
cryptography-based
authenticated encryption
versioned key support
key material outside PostgreSQL
key material outside Git
```

Не изобретать собственную криптографию.

Допустим MVP adapter уровня Fernet/MultiFernet, если контракт формально сохраняет возможность будущей замены key source на KMS/secret manager без изменения application API.

---

## Decision 5 — Transient Kaiten verification outage

Если credential verification временно невозможна:

```text
return retryable application error
existing Kaiten connection remains unchanged
new credential is not persisted
```

Не инвалидировать старое рабочее подключение только из-за временной недоступности Kaiten.

---

## Decision 6 — Explicit connection replacement

Замена существующего Kaiten credential/base URL выполняется только по **явной пользовательской команде**.

При конкурентных успешных replacement attempts:

```text
last committed verified replacement wins
```

Финальная запись должна сериализоваться через PostgreSQL row locking/re-check.

---

## Decision 7 — MAX chat rotation

Если:

```text
same max_user_id
new max_chat_id
```

то binding автоматически обновляется **только при однозначном отсутствии конфликта**:

```text
max_user_id уже принадлежит этому KVC user
new max_chat_id не принадлежит другому KVC user
PRIVATE identity semantics соблюдены
```

В противном случае:

```text
IdentityConflict
```

Для этого разрешено на будущем implementation stage добавить **узкий repository method** для lock/update существующего MAX binding.

Schema migration для этого не требуется.

---

# 5. Главная архитектурная граница

Финальная dependency direction должна быть зафиксирована как минимум так:

```text
transport
(MAX bot / future HTTP endpoints)
        ↓
kvc_application
        ↓
application ports + persistence repositories
        ↓
kvc_persistence
        ↓
SQLAlchemy / PostgreSQL
```

External integrations:

```text
Kaiten
MAX
GigaChat
SaluteSpeech
future secret/KMS provider
```

являются adapters.

Application layer не должен зависеть от provider SDK/client implementation.

---

# 6. Разрешённые и запрещённые зависимости application layer

## Разрешено

```text
Python standard library
typed application DTOs
application errors
application Protocol/ports
SQLAlchemy AsyncSession / async_sessionmaker types
kvc_persistence repositories
ORM entities, если они получены через repository contracts
```

## Запрещено

```text
Kaiten HTTP client implementation
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

Не вводить domain abstraction layer только ради формальной чистоты, если она не несёт реального поведения.

---

# 7. Итоговый состав application services

Зафиксировать минимальный набор:

```text
IdentityService
KaitenConnectionService
```

Не создавать service per table.

## `IdentityService`

Отвечает за:

```text
MAX private identity resolution
first-message KVC user onboarding
MAX binding conflict detection
safe MAX chat rotation
default notification settings creation
user lifecycle visibility during identity resolution
```

## `KaitenConnectionService`

Отвечает за:

```text
verified bind
verified replacement
disable
NEEDS_REAUTH lifecycle
secure credential retrieval for internal application workflows
disabled-user guard
transaction orchestration around connection state
```

Future command-processing services должны использовать эти контракты, а не обходить их.

---

# 8. `IdentityService` — frozen public contract

Основная операция:

```python
async def resolve_or_onboard_private_max_user(
    input: ResolveMaxIdentityInput,
) -> IdentityResolution: ...
```

## Input

```text
max_user_id: str
max_chat_id: str
chat_type: Literal["PRIVATE"]
```

На application level допустима дополнительная defensive validation, но provider SDK object в DTO не передавать.

## Output

Минимум:

```text
user_id: UUID
max_chat_binding_id: UUID
user_status: Literal["ACTIVE", "DISABLED"]
is_new_user: bool
kaiten_connection_status:
    Literal["ACTIVE", "DISABLED", "NEEDS_REAUTH"] | None
```

Не возвращать ORM/session objects наружу transport boundary.

---

# 9. MAX identity resolution algorithm

Финально зафиксировать следующий порядок:

```text
1. Lookup by incoming max_chat_id.
2. Если binding найден:
       require binding.max_user_id == incoming max_user_id.
3. Если binding по max_chat_id не найден:
       lookup existing PRIVATE binding by max_user_id.
4. Если найден binding по max_user_id:
       проверить возможность безопасной rotation/rebind max_chat_id.
5. Если не найден ни chat binding, ни user binding:
       создать новый KVC user.
6. Создать primary PRIVATE MAX binding.
7. Создать notification_settings defaults.
8. Получить current Kaiten connection status, если connection существует.
9. Commit transaction.
10. Вернуть IdentityResolution.
```

Conflict case:

```text
max_chat_id points to user A
max_user_id points to user B
```

должен завершаться:

```text
IdentityConflict
```

Никакой автоматический merge identity не выполнять.

---

# 10. MAX chat rotation contract

Спецификация должна точно определить safe-rebind flow.

Допустимое поведение:

```text
existing binding by max_user_id
new max_chat_id
new max_chat_id is unbound
same KVC user
PRIVATE
    =>
lock existing binding
re-check uniqueness/conflict
update max_chat_id
```

Недопустимо:

```text
steal max_chat_id from another user
merge two KVC users
create second primary binding accidentally
ignore max_user_id mismatch
```

Repository extension должна быть минимальной и относиться к `003-02`, а не к `003-00a`.

---

# 11. User lifecycle contract

Frozen user states:

```text
ACTIVE
DISABLED
```

## ACTIVE

Разрешено:

```text
identity resolution
Kaiten bind/rebind
explicit Kaiten commands
notification delivery if notification_settings.enabled = true
```

## DISABLED

Identity lookup всё ещё должен быть возможен:

```text
IdentityResolution.user_status = DISABLED
```

Но user-facing application operations должны отклоняться через:

```text
UserDisabled
```

Минимум запрещено:

```text
bind/replace Kaiten connection
execute user Kaiten command
receive background notifications
```

Не реализовывать deletion.

Административный re-enable path в branch `003` не добавлять, если его уже нет в принятой спецификации.

---

# 12. Notification settings onboarding contract

На first-message onboarding:

```text
users
max_chats
notification_settings
```

создаются в **одной DB transaction**.

`notification_settings`:

```text
enabled = false
due_soon_days = 1
timezone = UTC
```

Если retry/concurrent onboarding приходит после race loser rollback:

```text
повторный resolution должен вернуть уже существующий user/settings
```

Не включать notification worker implementation в эту ветку.

---

# 13. `KaitenConnectionService` — frozen public operations

Минимальный контракт:

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

Точную форму `MarkKaitenNeedsReauthInput` определить так, чтобы stale-credential race была устранима без schema change.

`get_active_connection_secret`:

- internal application method;
- не transport DTO;
- не логируется;
- возвращается только workflow, который непосредственно собирается вызвать Kaiten port.

---

# 14. Kaiten connection lifecycle

Frozen states:

```text
ACTIVE
DISABLED
NEEDS_REAUTH
```

Допустимые transitions:

```text
missing
    -> ACTIVE
    successful verified first bind

ACTIVE
    -> ACTIVE
    successful explicit verified replacement

ACTIVE
    -> NEEDS_REAUTH
    confirmed auth failure for the same credential snapshot

ACTIVE
    -> DISABLED
    explicit disable

NEEDS_REAUTH
    -> ACTIVE
    successful explicit verified rebind

NEEDS_REAUTH
    -> DISABLED
    explicit disable

DISABLED
    -> ACTIVE
    explicit verified rebind/re-enable action
```

Не добавлять новый persistence status.

---

# 15. Verification-before-persist flow

Успешный bind/replace должен иметь порядок:

```text
1. Transport validates outer input shape.
2. Application receives plaintext token as short-lived secret value.
3. Check user existence/status as needed without holding long DB locks.
4. Verify credential through KaitenCredentialVerifier.
5. Encrypt through TokenCipher.
6. Open short DB transaction.
7. Lock user row.
8. Re-check user.status == ACTIVE.
9. Lock existing kaiten_connections row, если есть.
10. Create/update connection.
11. Set status = ACTIVE.
12. Persist ciphertext + token_encryption_version.
13. Set last_verified_at = Clock.now().
14. Commit.
15. Return non-secret DTO.
```

Не держать DB row lock во время Kaiten network request.

---

# 16. Token plaintext boundary

Разрешено видеть plaintext token только следующим участникам:

```text
transport input handling
BindKaitenConnectionInput
KaitenConnectionService short-lived local scope
KaitenCredentialVerifier adapter
TokenCipher adapter
internal Kaiten adapter immediately before authenticated outbound call
```

Запрещено:

```text
repositories
ORM persisted plaintext
logs
repr
exceptions
reports
snapshots
test golden files
transport output
notification layer
worker scheduling state
database diagnostics
```

Plaintext secret field в dataclass обязательно:

```python
field(repr=False)
```

или эквивалентная безопасная реализация.

---

# 17. DTO contract

Предпочтительный стиль:

```text
frozen dataclasses
```

Application DTO не должны зависеть от Pydantic без доказанной необходимости.

Минимальный набор:

```text
ResolveMaxIdentityInput
IdentityResolution
BindKaitenConnectionInput
KaitenConnectionResult
ActiveKaitenConnectionSecret
KaitenCredentialVerification
EncryptedToken
MarkKaitenNeedsReauthInput
```

## Secret DTO rules

`BindKaitenConnectionInput`:

```text
plaintext token field repr=False
```

`ActiveKaitenConnectionSecret`:

```text
internal only
must not cross transport response boundary
plaintext field repr=False
```

`KaitenConnectionResult`:

не содержит:

```text
plaintext token
ciphertext
encryption key
Authorization data
```

---

# 18. Application ports

Зафиксировать минимум следующие ports.

## TokenCipher

```python
@dataclass(frozen=True)
class EncryptedToken:
    ciphertext: bytes
    version: int


class TokenCipher(Protocol):
    def encrypt(self, plaintext: str) -> EncryptedToken: ...

    def decrypt(self, ciphertext: bytes, version: int) -> str: ...
```

## KaitenCredentialVerifier

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

## Clock

```python
class Clock(Protocol):
    def now(self) -> datetime: ...
```

`Clock.now()` возвращает timezone-aware UTC.

Не добавлять port ради каждой простой функции.

---

# 19. Concrete crypto adapter contract

На `003-00a` определить, но **не реализовывать**:

```text
authenticated encryption
cryptography dependency
versioned key ring
active write key
read support for old versions during rotation
key material loaded outside kvc_application
no key material in PostgreSQL
no key material in Git
```

`token_encryption_version` означает:

```text
crypto/key version
```

и **не должен использоваться как logical credential revision**.

Это обязательное уточнение.

---

# 20. Critical stale-credential race contract

Обязательно зафиксировать отдельно.

Проблема:

```text
T1:
command reads credential A
calls Kaiten

T2:
user successfully replaces A -> B
connection remains ACTIVE

T1:
old request using A receives 401
```

Недопустимый результат:

```text
T1 marks current credential B as NEEDS_REAUTH
```

## Frozen rule

`mark_needs_reauth` может изменить status текущей connection только если application доказал, что authentication failure относится **к тому же credential snapshot**, который всё ещё хранится в connection.

### Нельзя использовать

```text
token_encryption_version
```

как revision credential, потому что разные plaintext tokens могут быть зашифрованы одним и тем же crypto key/version.

### MVP без schema migration

Выбрать и формализовать безопасный snapshot identifier из уже существующего persistence state.

Предпочтительный порядок выбора:

```text
1. existing reliable row revision/updated_at, если текущая модель гарантирует достаточную семантику;
или
2. internal encrypted credential snapshot:
       encrypted_api_token + token_encryption_version
   captured when secret was read;
или
3. другой уже существующий immutable-enough field combination,
   если audit repo докажет его корректность.
```

Не добавлять schema field только ради этого, если existing state достаточен.

### Required algorithm

```text
get_active_connection_secret:
    captures safe credential snapshot identifier
    returns it only internally together with plaintext secret

later auth failure:
    begin transaction
    lock current kaiten_connections row
    compare current connection with captured snapshot
    if snapshot differs:
        stale failure -> do not downgrade current connection
        return no-op/stale result
    if same snapshot and status is still ACTIVE:
        set NEEDS_REAUTH
        commit
```

Если connection уже:

```text
NEEDS_REAUTH
```

повторный mark должен быть idempotent.

Если connection:

```text
DISABLED
```

не переводить обратно/иначе из-за stale request.

Финальная спецификация должна выбрать **один точный implementation contract**, исходя из фактических полей модели `kaiten_connections`.

---

# 21. External-call and DB-transaction matrix

В итоговом документе обязательно дать таблицу:

| Use case | External call | DB transaction | Row lock | Ordering | Failure behavior |
|---|---|---|---|---|---|

Минимум для:

```text
resolve existing MAX identity
first-message onboarding
MAX chat rotation
first Kaiten bind
Kaiten replacement
disable connection
get active secret
mark NEEDS_REAUTH
```

Общее правило:

```text
external network call outside DB row-lock wait
short transaction for final state transition
re-check mutable guards under lock
```

---

# 22. Transaction ownership

Frozen rule:

```text
repositories do not own commit/rollback
application write method owns transaction boundary
```

Предпочтительный service construction:

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

Write methods используют:

```python
async with self._sessionmaker() as session:
    async with session.begin():
        ...
```

Не вводить скрытый global session.

Не вводить UnitOfWork abstraction без фактической необходимости.

---

# 23. Concurrency contract — MAX onboarding

Race:

```text
two first messages for same unknown MAX identity
```

Ожидаемое поведение:

```text
both may observe missing state
one transaction wins UNIQUE race
loser gets IntegrityError / persistence conflict
loser rolls back
loser retries identity lookup once
both requests ultimately resolve to same KVC user
```

Если после одного controlled retry state остаётся противоречивым:

```text
IdentityConflict
или
PersistenceConflict
```

в зависимости от фактической причины.

Не делать бесконечный retry loop.

---

# 24. Concurrency contract — token replacement

Race:

```text
two explicit verified replacements
```

Проверку каждого credential выполнять вне row lock.

Финальную запись:

```text
lock user
re-check ACTIVE user
lock connection
write verified replacement
```

Допустимая MVP semantics:

```text
last committed verified replacement wins
```

Не держать network call внутри retrying DB transaction.

---

# 25. Idempotency contract

Обязательно зафиксировать:

```text
same max_user_id + max_chat_id
    -> same KVC user

repeated eager settings creation
    -> one notification_settings row

safe repeated MAX rotation request
    -> same final binding

repeated verified bind of same logical credential/base URL
    -> one connection row, ACTIVE

repeated disable
    -> DISABLED

repeated mark_needs_reauth for same current credential
    -> NEEDS_REAUTH

stale mark_needs_reauth for replaced credential
    -> no-op
```

Не требовать global idempotency key subsystem в branch `003`.

---

# 26. Error taxonomy

Зафиксировать application-level hierarchy:

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

Допустимо добавить узкий internal error, если он реально необходим для stale-snapshot semantics, но не расширять taxonomy без причины.

---

# 27. Provider error mapping

Kaiten adapter/port boundary должен нормализовать ошибки:

```text
credential rejected / 401-style auth failure
    -> KaitenAuthenticationFailed

temporary timeout/network/5xx-like availability failure
    -> KaitenTemporarilyUnavailable

unexpected response/protocol violation
    -> KaitenVerificationFailed
```

Application errors не должны содержать:

```text
token
Authorization header
ciphertext
key material
raw provider body with secrets
full secret-bearing URL
```

Transport user-facing text относится к будущему MAX/API stage.

---

# 28. Persistence error mapping

Unique/concurrency violations не должны вытекать наружу как raw SQLAlchemy errors.

Зафиксировать mapping:

```text
known identity uniqueness conflict
    -> IdentityConflict

known retryable onboarding race
    -> retry once, then resolved result or PersistenceConflict

unexpected persistence invariant failure
    -> PersistenceConflict
```

Не скрывать реальные programming errors под generic retry loop.

---

# 29. Disabled-user guards

Спецификация должна отдельно показать matrix:

| Operation | ACTIVE | DISABLED |
|---|---:|---:|
| resolve identity | allow | allow/return status |
| onboard new identity | allow | n/a |
| rotate MAX chat | allow | resolve safely; no business re-enable |
| bind Kaiten | allow | reject |
| replace Kaiten | allow | reject |
| disable Kaiten | allow | define idempotent admin-safe behavior |
| get active secret for command | allow if ACTIVE connection | reject |
| send notification | allow if settings enabled | skip |

Background notification layer в будущем обязан проверять:

```text
users.status == ACTIVE
```

даже если:

```text
notification_settings.enabled == true
```

Не менять `NotificationSettingsRepository.list_enabled()` schema/contract только ради этого на `003-00a`; зафиксировать application/worker guard.

---

# 30. Security/redaction contract

Разрешено логировать:

```text
user_id
max_chat_binding_id
connection_id
status transition
safe provider status class
safe application error type
operation name
```

Запрещено:

```text
plaintext token
encrypted_api_token
crypto key
Authorization header
secret config values
full provider response containing auth material
repr DTO with plaintext
```

Report/tests не должны содержать реальные credentials.

---

# 31. Configuration and dependency injection boundary

`kvc_application` не загружает `.env`.

Composition root:

```text
API startup
worker startup
dedicated dependency wiring module
```

может:

```text
load AppSettings
construct AsyncSession maker
construct TokenCipher adapter
construct KaitenCredentialVerifier adapter
construct Clock
construct application services
```

Не создавать provider clients внутри service methods.

---

# 32. Out of scope branch 003-00a

Не проектировать и не реализовывать:

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

---

# 33. Repository-contract extension allowed for future implementation

В `003-00a` только специфицировать future narrow extensions, если текущих repository methods недостаточно.

Минимально допустимый кандидат:

```text
MaxChatRepository:
    lock/update existing PRIVATE binding max_chat_id
```

Для stale credential flow определить, достаточно ли существующего:

```text
KaitenConnectionRepository FOR UPDATE path
```

Если достаточно — новых repository methods не придумывать.

Если требуется narrow compare-and-mark primitive, описать его contract, но не реализовывать на `003-00a`.

---

# 34. Testing contract for future stages

На этом этапе tests не писать, но подготовить frozen acceptance matrix.

## Unit

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
NEEDS_REAUTH
decrypt failure
stale mark_needs_reauth no-op
current credential auth failure -> NEEDS_REAUTH
```

## PostgreSQL integration

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

## Security

```text
plaintext absent from DB
plaintext absent from repr
plaintext absent from logs/errors
ciphertext persisted
wrong encryption version/key fails safely
non-secret output DTO
```

---

# 35. Planned implementation decomposition

Проверить и окончательно зафиксировать план:

```text
003-00   audit
003-00a  final application service/user onboarding specification
003-01   application DTO/port/error contracts implementation
003-02   IdentityService + MAX binding onboarding/rotation implementation
003-03   TokenCipher contract + cryptography adapter implementation
003-04   KaitenConnectionService + credential lifecycle implementation
003-05   full application service acceptance
003-06   branch acceptance / Git integration / closeout
```

Допустимо уточнить границы соседних stages, но не дробить ветку без необходимости.

Каждый этап должен иметь один чёткий acceptance target.

---

# 36. Что нельзя делать на `003-00a`

Запрещено:

- менять production Python code;
- создавать DTO/Protocol/error classes;
- создавать services;
- реализовывать repository extension;
- реализовывать crypto adapter;
- делать live Kaiten call;
- делать live MAX call;
- добавлять dependencies;
- менять schema;
- создавать Alembic revision;
- делать DDL/DML;
- менять `.env`;
- добавлять real secrets;
- переключать Git branch автоматически;
- выполнять Git commit;
- начинать `003-01`.

Этот этап должен оставить production behavior неизменным.

---

# 37. Обязательный итоговый документ

Создай:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
```

Документ должен быть **самодостаточной implementation specification**, а не коротким дополнением к `003-00`.

Минимальная структура:

1. Executive summary.
2. Accepted user decisions.
3. Frozen persistence/repository baseline.
4. Layer/dependency contract.
5. Final service inventory.
6. `IdentityService` contract.
7. MAX identity resolution algorithm.
8. MAX chat rotation contract.
9. User lifecycle/disabled-user matrix.
10. Notification settings onboarding contract.
11. `KaitenConnectionService` contract.
12. Kaiten connection state machine.
13. Verification-before-persist contract.
14. Token plaintext/security boundary.
15. DTO contracts.
16. Port contracts.
17. Crypto/key-version contract.
18. Stale-credential snapshot contract.
19. `mark_needs_reauth` algorithm.
20. External-call/transaction matrix.
21. Transaction ownership.
22. Concurrency invariants.
23. Idempotency contract.
24. Error taxonomy.
25. Provider/persistence error mapping.
26. Dependency injection/composition root.
27. Repository extensions required by future implementation.
28. Future testing matrix.
29. Implementation-stage decomposition.
30. Explicit out-of-scope list.
31. Consistency review.
32. Changed files.
33. Quality gate.
34. Final status.

---

# 38. Mandatory consistency review

Перед финальным статусом проверить минимум:

1. Application layer не зависит от provider implementation.
2. Repositories по-прежнему не commit/rollback.
3. Нет schema changes.
4. First-message onboarding атомарно создаёт user + MAX binding + notification settings.
5. `enabled=false` предотвращает неожиданные notifications.
6. Identity resolution идемпотентен.
7. MAX rotation не может steal чужой chat binding.
8. Disabled user не может rebind Kaiten через user-facing flow.
9. Credential verification выполняется до persistence.
10. Transient Kaiten outage не разрушает existing ACTIVE connection.
11. Plaintext token не пересекает persistence boundary.
12. Ciphertext/key material не попадают в public DTO.
13. `token_encryption_version` трактуется только как crypto version.
14. Stale auth failure не может downgrade freshly replaced credential.
15. `mark_needs_reauth` использует exact credential snapshot semantics.
16. Network call не выполняется под длительным row lock.
17. Concurrent replacements имеют однозначную winner semantics.
18. Provider raw exceptions не выходят за adapter/application boundary.
19. No local Kaiten content cache introduced.
20. Implementation stages не содержат скрытых product decisions.

---

# 39. Baseline quality gate

Production code изменяться не должен.

Выполни:

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
```

Ожидаемый baseline из `003-00`:

```text
Python 3.12.9
pip check PASS
pytest: 61 passed
pytest -W error: 61 passed
ruff format PASS
ruff check PASS
mypy PASS
Alembic current = 00201_mvp_service_model
Alembic check = no new upgrade operations
git diff --check PASS
```

Количество файлов может отличаться из-за появления prompt/report `003-00a`.

Если baseline изменился по объективной причине, описать фактическое состояние, но не исправлять unrelated issues автоматически.

---

# 40. Git discipline

Не выполнять commit.

В report показать:

```text
git branch --show-current
git status --short
git diff --check
git diff --stat
```

Классифицировать изменения:

```text
Production code:
Tests:
Alembic/schema:
Dependencies:
Configuration:
Documentation:
Prompts:
Reports:
Other:
```

Ожидаемо:

```text
Production code:
none

Tests:
none

Alembic/schema:
none

Dependencies:
none
```

Допустимы только specification/report artifacts данного этапа.

---

# 41. Критерий завершения

`003-00a` считается завершённым только если:

- все семь пользовательских решений зафиксированы как frozen;
- application dependency direction однозначен;
- `IdentityService` полностью специфицирован;
- MAX onboarding алгоритм однозначен;
- MAX chat rotation не оставляет race/conflict ambiguity;
- eager notification settings creation зафиксировано;
- `KaitenConnectionService` полностью специфицирован;
- state transitions однозначны;
- verification-before-persist contract однозначен;
- transient outage behavior однозначен;
- plaintext/ciphertext/key boundaries однозначны;
- `TokenCipher` и `KaitenCredentialVerifier` ports однозначны;
- transaction ownership однозначен;
- network/DB ordering однозначен;
- concurrency/idempotency rules однозначны;
- disabled-user guards однозначны;
- stale credential race закрыта без misuse `token_encryption_version`;
- `mark_needs_reauth` имеет реализационно пригодный compare-and-mark contract;
- не требуется schema migration;
- future repository extensions минимальны;
- `003-01` можно начинать без нового архитектурного решения;
- production code не изменён;
- quality gate пройден либо объективно описан baseline blocker.

---

# 42. Ожидаемый финальный статус

Если все принятые решения удалось непротиворечиво зафиксировать:

```text
ACCEPTED SPECIFICATION — READY FOR 003-01
```

Если фактическая persistence model не позволяет безопасно закрыть stale-credential contract без schema change или обнаружено иное реальное противоречие:

```text
BLOCKED — USER DECISION REQUIRED
```

В этом случае:

- не начинать implementation;
- не менять schema самостоятельно;
- перечислить только конкретный blocker;
- показать минимальные варианты его устранения.

---

## Главное правило этапа

`003-00a` должен **заморозить application-service/user-onboarding contract** ветки `003`.

После принятия отчёта:

```text
003-01
```

должен быть чистой реализацией DTO/ports/errors без повторного архитектурного проектирования.
