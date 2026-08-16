# 003-01 — Application DTO, port and error contracts implementation

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Функциональная ветка:

```text
003 — Application service layer and user onboarding
```

Предыдущие этапы завершены и приняты:

```text
003-00   Application service/user onboarding audit
003-00a  Final application service/user onboarding specification
```

Главный нормативный документ этого этапа:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
```

Его финальный статус:

```text
ACCEPTED SPECIFICATION - READY FOR 003-01
```

На этом этапе необходимо **реализовать только типизированные application contracts**:

```text
DTOs
application errors
Protocol ports
public package exports
contract/unit tests
implementation report
```

Это **реализационный этап**, но пока ещё **не реализация application services**.

Не реализовывать:

```text
IdentityService
KaitenConnectionService
MAX binding workflow
TokenCipher adapter
Kaiten HTTP verifier adapter
crypto/key loading
live Kaiten calls
live MAX calls
```

---

# 1. Главная цель

После `003-01` пакет:

```text
src/kvc_application/
```

должен содержать стабильный, типизированный и безопасный контракт, на который смогут опираться следующие этапы:

```text
003-02 — IdentityService
003-03 — TokenCipher adapter
003-04 — KaitenConnectionService
```

Целевой dependency contract:

```text
future transports/adapters
        ↓
kvc_application DTOs / errors / ports
        ↓
future application services
```

На этом этапе application contracts должны быть:

- importable;
- type-checkable;
- provider-neutral;
- persistence-neutral в DTO/API semantics;
- secret-safe;
- frozen;
- минимальными;
- полностью соответствующими `003-00a`.

Не добавлять бизнес-поведение ради удобства тестов.

---

# 2. Нормативные документы и приоритет

Перед изменением кода обязательно изучи:

```text
codex/reports/003_00_application_service_user_onboarding_audit_report.md
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
```

Также изучи persistence baseline:

```text
codex/reports/002_03_repository_query_contracts_implementation_report.md
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

Проверь текущие:

```text
src/kvc_application/
src/kvc_domain/
src/kvc_integrations/
src/kvc_persistence/
tests/
pyproject.toml
AGENTS.md
README.md
```

Приоритет:

```text
003-00a  — frozen implementation contract
003-00   — audit/rationale
002-04   — accepted branch/persistence baseline
002-03   — repository contract details
```

Если кодовая база отличается от ожидаемой структуры, адаптируй только размещение файлов, **не меняя frozen semantics**.

Если найдено реальное противоречие с `003-00a`, не проектируй новый контракт самостоятельно:

```text
BLOCKED - FROZEN CONTRACT CONFLICT
```

и зафиксируй blocker в report.

---

# 3. Сначала открыть рабочую ветку 003

По `003-00a` ожидаемый исходный Git state:

```text
current branch:
002-mvp-service-data-model

HEAD:
accepted closeout of branch 002

untracked 003 specification artifacts may already exist
```

Целевое имя новой ветки:

```text
003-application-service-user-onboarding
```

Перед любыми действиями выполнить:

```powershell
git status --short
git status --ignored --short
git branch --show-current
git branch --list
git log --oneline --decorate --graph -10
git diff --check
git diff --stat
git diff --name-status
```

## Если ветка `003-application-service-user-onboarding` ещё не существует

Если текущий HEAD действительно является accepted HEAD закрытой ветки `002`, создать:

```powershell
git switch -c 003-application-service-user-onboarding
```

Переключение должно сохранить существующие untracked artifacts `003-00/003-00a`.

После переключения проверить:

```powershell
git branch --show-current
git status --short
git log --oneline --decorate -5
```

## Если ветка уже существует

Не создавать дубликат.

Проверить:

```text
branch base
current HEAD
existing worktree
existing branch changes
```

Переключиться только если это безопасно.

Запрещено использовать для "починки":

```text
git reset --hard
git clean -fd
git checkout .
git restore .
force checkout
force branch overwrite
```

Если есть риск потери worktree:

```text
BLOCKED - EXISTING BRANCH/WORKTREE CONFLICT
```

---

# 4. Branch base verification

После открытия/перехода на ветку проверить:

```powershell
git merge-base 002-mvp-service-data-model HEAD
git log --oneline --decorate --graph --all -15
```

Ожидается, что `003` начинается от accepted closeout HEAD ветки:

```text
002-mvp-service-data-model
```

Не делать rebase автоматически.

Не merge в `main`.

Не push.

---

# 5. Frozen scope `003-01`

Разрешено создавать/изменять только логически необходимые application-contract files.

Предпочтительная структура:

```text
src/kvc_application/__init__.py
src/kvc_application/dto.py
src/kvc_application/errors.py
src/kvc_application/ports.py
```

Допустимы минимальные изменения существующего package layout, если текущие project conventions требуют другого размещения.

Tests — в существующем test layout, например:

```text
tests/unit/test_application_dto_contracts.py
tests/unit/test_application_error_contracts.py
tests/unit/test_application_port_contracts.py
```

или эквивалентная текущим conventions структура.

Не создавать сейчас:

```text
src/kvc_application/services/
src/kvc_integrations/kaiten/... implementation
src/kvc_integrations/... crypto implementation
new repository implementation
new migrations
```

---

# 6. Application DTO implementation style

Использовать:

```python
from dataclasses import dataclass, field
```

DTO должны быть:

```python
@dataclass(frozen=True)
```

если далее явно не указано иное.

Не использовать Pydantic внутри `kvc_application` на этом этапе.

Не добавлять runtime validation framework.

Не вводить custom base DTO class.

Не вводить serialization/deserialization framework.

DTO — это typed internal contracts, а не transport schemas.

---

# 7. Status type aliases

Для исключения дублирования допускается и рекомендуется определить компактные aliases:

```python
from typing import Literal

MaxChatType = Literal["PRIVATE"]

UserStatus = Literal[
    "ACTIVE",
    "DISABLED",
]

KaitenConnectionStatus = Literal[
    "ACTIVE",
    "DISABLED",
    "NEEDS_REAUTH",
]
```

Можно использовать другое безопасное размещение внутри `dto.py`, если оно не создаёт отдельный лишний module.

Не вводить Python `Enum`, если для этого нет уже принятой convention.

Физические persistence statuses остаются строковыми.

---

# 8. `ResolveMaxIdentityInput`

Реализовать frozen DTO:

```python
@dataclass(frozen=True)
class ResolveMaxIdentityInput:
    max_user_id: str
    max_chat_id: str
    chat_type: MaxChatType
```

Contract:

```text
MAX scope = PRIVATE only
provider SDK object не входит в DTO
transport metadata не входит в DTO
```

На этом этапе не добавлять custom `__post_init__` validation без необходимости.

---

# 9. `IdentityResolution`

Реализовать:

```python
@dataclass(frozen=True)
class IdentityResolution:
    user_id: UUID
    max_chat_binding_id: UUID
    user_status: UserStatus
    is_new_user: bool
    kaiten_connection_status: KaitenConnectionStatus | None
```

Не включать:

```text
ORM User
ORM MaxChat
AsyncSession
provider object
plaintext/ciphertext
```

---

# 10. `BindKaitenConnectionInput`

Реализовать:

```python
@dataclass(frozen=True)
class BindKaitenConnectionInput:
    user_id: UUID
    api_base_url: str
    plaintext_token: str = field(repr=False)
```

Критический security contract:

```text
plaintext_token must not appear in repr()
```

Не переименовывать в generic `token`, если frozen specification использует:

```text
plaintext_token
```

Не логировать DTO целиком в tests/report.

---

# 11. `KaitenConnectionResult`

Реализовать non-secret output DTO:

```python
@dataclass(frozen=True)
class KaitenConnectionResult:
    connection_id: UUID
    user_id: UUID
    status: KaitenConnectionStatus
    api_base_url: str
    kaiten_user_id: str | None
    workspace_id: str | None
    last_verified_at: datetime | None
```

Не включать:

```text
plaintext_token
encrypted_api_token
token_encryption_version
crypto key
Authorization metadata
snapshot
```

`last_verified_at` contract:

```text
timezone-aware UTC when populated by future service
```

На DTO stage не добавлять timezone conversion/validation logic.

---

# 12. `KaitenCredentialSnapshot`

Реализовать internal frozen DTO:

```python
@dataclass(frozen=True)
class KaitenCredentialSnapshot:
    connection_id: UUID
    encrypted_api_token: bytes = field(repr=False)
    token_encryption_version: int
```

Security:

```text
encrypted_api_token must not appear in repr()
snapshot is internal only
snapshot must never become transport output
```

Семантика:

```text
connection_id
+
encrypted_api_token
+
token_encryption_version
```

— это future stale-credential snapshot identifier.

Критически важно:

```text
token_encryption_version
```

означает **crypto/key version**, а не logical credential revision.

Не добавлять hash/revision/version column abstraction.

---

# 13. `ActiveKaitenConnectionSecret`

Реализовать:

```python
@dataclass(frozen=True)
class ActiveKaitenConnectionSecret:
    connection_id: UUID
    user_id: UUID
    api_base_url: str
    plaintext_token: str = field(repr=False)
    snapshot: KaitenCredentialSnapshot = field(repr=False)
```

Оба поля:

```text
plaintext_token
snapshot
```

не должны отображаться в `repr()`.

Этот DTO:

```text
internal application API only
```

Не экспортировать его как transport schema.

Можно экспортировать из `kvc_application` как application contract, если это соответствует package public API, но report должен явно отметить его internal-use semantics.

---

# 14. `MarkKaitenNeedsReauthInput`

Frozen specification определяет:

```python
@dataclass(frozen=True)
class MarkKaitenNeedsReauthInput:
    user_id: UUID
    snapshot: KaitenCredentialSnapshot
    reason: str
```

Рекомендуется скрыть snapshot из repr:

```python
snapshot: KaitenCredentialSnapshot = field(repr=False)
```

Также безопасно скрыть diagnostic `reason` из repr:

```python
reason: str = field(repr=False)
```

если это не ломает frozen field contract.

Важно:

```text
reason remains str in 003-01
```

Не вводить новый enum/code taxonomy без отдельного решения.

Но `reason` должен трактоваться как:

```text
internal sanitized diagnostic reason
```

Запрещено передавать туда:

```text
raw provider response
Authorization header
plaintext token
ciphertext
secret-bearing URL
exception dump containing credentials
```

На этом этапе никакое логирование `reason` не реализовывать.

---

# 15. `KaitenCredentialVerification`

Реализовать:

```python
@dataclass(frozen=True)
class KaitenCredentialVerification:
    kaiten_user_id: str | None
    workspace_id: str | None
```

Не добавлять provider response body или HTTP metadata.

---

# 16. `EncryptedToken`

Реализовать:

```python
@dataclass(frozen=True)
class EncryptedToken:
    ciphertext: bytes = field(repr=False)
    version: int
```

Frozen port semantics:

```text
ciphertext
version = crypto/key version
```

Хотя это internal DTO, ciphertext также не должен отображаться в repr.

Не добавлять:

```text
key id text
algorithm field
nonce field
logical credential revision
```

если этого не требует конкретный будущий adapter contract.

---

# 17. DTO repr-security tests

Добавить targeted tests, которые используют только **synthetic fake values**.

Обязательно доказать, что:

```text
BindKaitenConnectionInput repr
    does not contain plaintext token

ActiveKaitenConnectionSecret repr
    does not contain plaintext token
    does not expose snapshot

KaitenCredentialSnapshot repr
    does not contain ciphertext bytes

EncryptedToken repr
    does not contain ciphertext bytes

MarkKaitenNeedsReauthInput repr
    does not expose snapshot
```

Если `reason` скрыт через `repr=False`, проверить и это.

Использовать заведомо фиктивные строки:

```text
test-token-do-not-use
```

или аналогичные.

Никаких live credentials.

---

# 18. Frozen dataclass tests

Для DTO проверить:

```text
dataclass
frozen
field inventory
field order where relevant
```

Targeted test может доказать frozen semantics через:

```python
dataclasses.FrozenInstanceError
```

Не писать brittle tests на полный `repr()` string, если достаточно проверить отсутствие secret values.

Не тестировать внутренности stdlib dataclasses сверх нужного контракта.

---

# 19. Application error hierarchy

Реализовать:

```python
class ApplicationError(Exception):
    """Base application-layer error."""
```

И прямые/логичные subclasses:

```text
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

Минимальный допустимый shape:

```python
class IdentityConflict(ApplicationError):
    pass
```

и аналогично.

Не добавлять сложный error payload framework.

Не добавлять HTTP status code внутрь application errors.

Не добавлять MAX-specific text внутрь errors.

Не добавлять raw provider exceptions как public fields.

---

# 20. Error taxonomy tests

Проверить:

```text
all frozen error classes importable
all are subclasses of ApplicationError
ApplicationError is subclass of Exception
errors are distinct classes
```

Дополнительно проверить, что простое создание exception не требует provider-specific аргументов.

Не навязывать конкретные user-facing messages.

Transport mapping будет позже.

---

# 21. `TokenCipher` port

Реализовать через `typing.Protocol`:

```python
class TokenCipher(Protocol):
    def encrypt(self, plaintext: str) -> EncryptedToken: ...

    def decrypt(self, ciphertext: bytes, version: int) -> str: ...
```

Contract:

```text
sync interface
provider-neutral
no config loading
no key loading
no cryptography implementation here
```

Не импортировать `cryptography` в `ports.py`.

Не реализовывать Fernet на `003-01`.

---

# 22. `KaitenCredentialVerifier` port

Реализовать:

```python
class KaitenCredentialVerifier(Protocol):
    async def verify(
        self,
        *,
        api_base_url: str,
        plaintext_token: str,
    ) -> KaitenCredentialVerification: ...
```

Contract:

```text
async
keyword-only api_base_url/plaintext_token
returns normalized application DTO
no provider response type
```

Не реализовывать network request.

Не импортировать HTTP/Kaiten client.

---

# 23. `Clock` port

Реализовать:

```python
class Clock(Protocol):
    def now(self) -> datetime: ...
```

Contract:

```text
future implementation returns timezone-aware UTC
```

На `003-01` реальный clock adapter не нужен.

Не использовать global `datetime.now()` внутри port module.

---

# 24. Protocol implementation rules

Ports должны быть:

```text
structural typing contracts
```

Не создавать abstract base class hierarchy.

Не создавать factory.

Не создавать dependency injection container.

Не добавлять `@runtime_checkable`, если tests/runtime реально этого не требуют.

Не создавать fake implementation в production source.

Test-only small fakes допустимы.

---

# 25. Port contract tests

Добавить targeted tests минимум на:

```text
ports import cleanly
port method names present
TokenCipher encrypt/decrypt signatures соответствуют contract
KaitenCredentialVerifier.verify is async
verify parameters are keyword-only after self
Clock.now is sync
return annotations point to application DTOs
```

Не делать tests чрезмерно зависимыми от formatting/implementation details.

Если structural fake tests проще и устойчивее, использовать их.

Не требовать live provider.

---

# 26. Package public API

Проверить текущую convention `src/kvc_application/__init__.py`.

Если package уже использует explicit exports — добавить согласованный export surface.

Предпочтительно предоставить удобные imports:

```python
from kvc_application.dto import ...
from kvc_application.errors import ...
from kvc_application.ports import ...
```

и при необходимости re-export из package root.

Не создавать wildcard side effects.

Если используешь `__all__`, он должен быть точным и не содержать future services/adapters.

Не экспортировать provider code.

---

# 27. Import/dependency hygiene

После implementation `kvc_application` не должен импортировать:

```text
kvc_integrations
Kaiten client
MAX client
GigaChat client
SaluteSpeech client
cryptography implementation
httpx/provider HTTP implementation
pydantic transport schemas
AppSettings
.env loader
```

На этом этапе также не требуется импортировать repositories.

DTO/ports/errors должны оставаться независимо importable.

Допускаются:

```text
dataclasses
datetime
typing
uuid
```

и другие stdlib typing helpers.

---

# 28. Persistence baseline не менять

На `003-01` запрещено менять:

```text
src/kvc_persistence/models.py
src/kvc_persistence/repositories/
Alembic revisions
database schema
```

Не добавлять repository methods для MAX rotation — это `003-02`.

Не добавлять stale credential compare-and-mark helper — это `003-04`, только если вообще понадобится.

Alembic head должен остаться:

```text
00201_mvp_service_model
```

---

# 29. Не реализовывать `IdentityService`

На этом этапе не создавать:

```python
class IdentityService: ...
```

Не реализовывать:

```text
resolve_or_onboard_private_max_user
first-message transaction
MAX binding lookup
MAX chat rotation
notification settings creation
race retry
```

Это следующий этап:

```text
003-02
```

DTO/error/port design не должен случайно тянуть service implementation вперёд.

---

# 30. Не реализовывать crypto adapter

На `003-01`:

```text
TokenCipher = Protocol only
EncryptedToken = DTO only
```

Не реализовывать:

```text
Fernet
MultiFernet
AES-GCM
key ring
environment key parsing
KMS integration
decrypt/encrypt behavior
```

Это относится к:

```text
003-03
```

Не добавлять/обновлять dependency `cryptography`, если она уже существует или если adapter ещё не нужен.

---

# 31. Не реализовывать `KaitenConnectionService`

На этом этапе не создавать:

```text
bind_or_replace_connection
disable_connection
get_active_connection_secret behavior
mark_needs_reauth behavior
DB transactions
row locks
credential verification orchestration
```

Это относится к:

```text
003-04
```

`KaitenCredentialSnapshot` и input/output DTOs реализуются сейчас только как contracts.

---

# 32. No live external operations

Запрещено:

```text
live Kaiten API call
live MAX call
GigaChat call
SaluteSpeech call
network credential verification
provider mutation
```

Tests должны быть полностью offline/provider-free.

---

# 33. No database mutation

На `003-01` configured PostgreSQL не мутировать.

Запрещено:

```text
alembic upgrade
alembic downgrade
DDL
DML
test inserts into configured kvc_dev
manual schema patch
```

Разрешены read-only diagnostics:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

---

# 34. Security tests — mandatory

Добавить explicit regression assertions:

```text
plaintext fake token not in repr(BindKaitenConnectionInput)
plaintext fake token not in repr(ActiveKaitenConnectionSecret)
fake ciphertext not in repr(KaitenCredentialSnapshot)
fake ciphertext not in repr(EncryptedToken)
snapshot secret material not visible through parent DTO repr
```

Также убедиться, что exception classes сами по себе не сериализуют secret fields, потому что у них нет secret-bearing structured payload.

Не создавать logger assertions, если production logging ещё отсутствует.

---

# 35. Type safety

Новый source должен проходить:

```text
mypy src
```

Не использовать массово:

```text
Any
cast(...)
# type: ignore
```

только ради прохождения проверки.

Не создавать type alias, который размывает frozen status literals до plain `str`.

---

# 36. Formatting/lint

Новый code должен проходить:

```text
ruff format --check .
ruff check .
```

Не изменять unrelated files только ради общего reformat, кроме объективно необходимых files, затронутых этой задачей.

Если `ruff format --check .` падает на существующем markdown Python snippet, сначала определить, относится ли это к уже известному untracked prompt artifact. Допустимо минимально форматировать только такой stage artifact, как это уже произошло на `003-00a`, но report должен явно это указать.

Не массово форматировать unrelated repository documentation.

---

# 37. Tests — обязательный минимум

Добавь тесты, покрывающие минимум:

## DTO inventory

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
```

## Frozen semantics

```text
all DTOs frozen
mutation raises FrozenInstanceError
```

Не обязательно мутировать каждый DTO отдельно, если есть надёжный parameterized test.

## Secret repr

```text
plaintext hidden
ciphertext hidden
snapshot hidden where required
```

## Status literals

Проверить annotations/public typing contract без runtime enum conversion.

## Error inventory

Проверить всю frozen hierarchy.

## Port inventory

```text
TokenCipher
KaitenCredentialVerifier
Clock
```

## Async/sync contract

```text
verify = async
encrypt/decrypt/now = sync
```

## Import smoke

Проверить application contract imports через стандартный package path.

---

# 38. Не добавлять meaningless runtime validation

Не писать production code вида:

```python
if chat_type != "PRIVATE":
    raise ...
```

в DTO constructor только для того, чтобы "использовать" Literal.

Runtime orchestration/validation будет происходить в transport/service stages.

DTO stage должен оставаться declarative.

---

# 39. Exact frozen field inventory

Итоговая field inventory должна быть:

## ResolveMaxIdentityInput

```text
max_user_id
max_chat_id
chat_type
```

## IdentityResolution

```text
user_id
max_chat_binding_id
user_status
is_new_user
kaiten_connection_status
```

## BindKaitenConnectionInput

```text
user_id
api_base_url
plaintext_token
```

## KaitenConnectionResult

```text
connection_id
user_id
status
api_base_url
kaiten_user_id
workspace_id
last_verified_at
```

## KaitenCredentialSnapshot

```text
connection_id
encrypted_api_token
token_encryption_version
```

## ActiveKaitenConnectionSecret

```text
connection_id
user_id
api_base_url
plaintext_token
snapshot
```

## MarkKaitenNeedsReauthInput

```text
user_id
snapshot
reason
```

## KaitenCredentialVerification

```text
kaiten_user_id
workspace_id
```

## EncryptedToken

```text
ciphertext
version
```

Не добавлять hidden product fields.

---

# 40. Error inventory — exact

Итоговый public error inventory:

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

Не добавлять:

```text
HTTPError
MaxError
DatabaseError
ProviderError
AuthenticationError generic
RetryError generic
```

если это не требует frozen contract.

---

# 41. Port inventory — exact

Итоговый application port inventory:

```text
TokenCipher
KaitenCredentialVerifier
Clock
```

Не добавлять сейчас:

```text
MaxClient
KaitenCardClient
NotificationSender
LLMClient
STTClient
UnitOfWork
RepositoryFactory
```

---

# 42. Baseline quality gate before implementation

До изменения source выполнить:

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

Ожидаемый accepted baseline из `003-00a`:

```text
Python 3.12.9
pip check PASS
pytest: 61 passed
pytest -W error: 61 passed
ruff PASS
mypy PASS
Alembic current = 00201_mvp_service_model
Alembic check = no new upgrade operations detected
```

Количество files может отличаться из-за untracked `003` prompts/reports.

Если baseline объективно отличается, зафиксировать фактическое состояние.

Не исправлять unrelated functional defects автоматически.

---

# 43. Targeted test gate

После реализации сначала выполнить targeted tests нового contract layer, например:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_application_dto_contracts.py
.venv\Scripts\python.exe -m pytest tests/unit/test_application_error_contracts.py
.venv\Scripts\python.exe -m pytest tests/unit/test_application_port_contracts.py
```

Адаптировать пути к фактической test structure.

Показать:

```text
collected
passed
warnings
```

Warnings не игнорировать.

---

# 44. Full quality gate after implementation

После targeted tests выполнить:

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

Ожидается:

```text
test count > 61
0 warnings
Ruff PASS
mypy PASS
Alembic unchanged
no schema drift
```

---

# 45. Changed-files audit

Перед report сформировать полный inventory.

Ожидаемые categories:

```text
Production code:
  src/kvc_application/...

Tests:
  tests/... application contract tests

Alembic/schema:
  none

Dependencies:
  none

Configuration:
  none

Prompts:
  003 artifacts only

Reports:
  003_01 application contracts report

Other:
  none
```

Если изменился persistence/integration module — отдельно объяснить, почему. Ожидаемо этого быть не должно.

---

# 46. Secret audit

До финального статуса проверить новые/изменённые files на:

```text
real Kaiten token
Authorization
Bearer
real encryption key
real database password
real secret config value
```

Synthetic test strings допустимы только если явно выглядят фиктивными.

Проверить staged/unstaged/untracked content вручную безопасным search способом.

Не печатать в report найденный секрет, если он неожиданно обнаружен.

Если обнаружен реальный secret:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

---

# 47. Git discipline

На `003-01`:

```text
branch creation is allowed and required
implementation changes are allowed
Git commit is NOT required
push is forbidden
merge is forbidden
```

Не делать commit автоматически.

Ветка должна остаться:

```text
003-application-service-user-onboarding
```

с implementation/report changes в worktree для последующей приемки.

Не использовать:

```text
git add .
git commit
git push
git merge
git rebase
```

без отдельной задачи closeout/integration.

---

# 48. Implementation report

Создай:

```text
codex/reports/003_01_application_service_contracts_implementation_report.md
```

Report должен содержать минимум:

1. Executive summary.
2. Frozen contract source and precedence.
3. Initial Git/branch/worktree state.
4. Branch creation/switch result.
5. Branch-base verification.
6. Baseline quality gate.
7. Final application package layout.
8. DTO inventory.
9. Exact DTO field inventory.
10. Frozen dataclass semantics.
11. Status type aliases.
12. Secret `repr` protections.
13. `KaitenCredentialSnapshot` contract.
14. Confirmation `token_encryption_version` is crypto version only.
15. `MarkKaitenNeedsReauthInput` contract.
16. Error hierarchy inventory.
17. Port inventory.
18. `TokenCipher` signature.
19. `KaitenCredentialVerifier` signature.
20. `Clock` signature.
21. Package export surface.
22. Dependency/import hygiene.
23. Confirmation no provider implementation exists.
24. Confirmation no services implemented.
25. Confirmation no crypto adapter implemented.
26. Confirmation no persistence/schema changes.
27. Tests added.
28. Targeted test results.
29. Full quality gate.
30. Alembic unchanged state.
31. Secret audit.
32. Changed-file classification.
33. Explicit deferred work for `003-02/03/04`.
34. Final status.

---

# 49. Report security

В report запрещено включать:

```text
plaintext tokens
ciphertext values
environment secrets
database password
Authorization headers
crypto key values
raw provider responses
```

Для repr-security tests описывать только:

```text
secret absent from repr: PASS
```

Не вставлять полный test object repr, если там есть риск secret leakage.

---

# 50. Acceptance criteria

`003-01` успешен только если:

- рабочая ветка `003-application-service-user-onboarding` безопасно открыта от accepted `002` HEAD;
- untracked `003-00/003-00a` artifacts не потеряны;
- реализован `dto.py` или эквивалент;
- все девять frozen DTO contracts присутствуют;
- DTOs frozen;
- `Literal` status contracts сохранены;
- plaintext fields используют safe repr handling;
- ciphertext fields используют safe repr handling;
- snapshot скрыт из parent secret-bearing DTO repr;
- `token_encryption_version` не превращён в logical credential revision;
- `reason` остаётся `str` и не расширяется raw provider payload semantics;
- реализована exact application error hierarchy;
- реализованы ровно три required ports;
- `KaitenCredentialVerifier.verify` async;
- `TokenCipher.encrypt/decrypt` sync;
- `Clock.now` sync;
- application contracts не зависят от provider implementation;
- Pydantic не введён в application DTO без необходимости;
- не реализован `IdentityService`;
- не реализован `KaitenConnectionService`;
- не реализован crypto adapter;
- не изменены repositories;
- не изменена schema;
- не создана migration;
- dependencies не изменены;
- live Kaiten/MAX calls отсутствуют;
- configured PostgreSQL не мутировал;
- targeted tests проходят;
- full pytest проходит;
- `pytest -W error` проходит;
- Ruff проходит;
- mypy проходит;
- Alembic current остаётся `00201_mvp_service_model`;
- Alembic check показывает no drift;
- secret audit PASS;
- implementation report создан.

---

# 51. Final status

Если всё успешно:

```text
IMPLEMENTED - READY FOR 003-02 IDENTITY ONBOARDING SERVICE
```

Если frozen contract невозможно реализовать без изменения архитектуры:

```text
BLOCKED - FROZEN CONTRACT CONFLICT
```

Если Git branch/worktree нельзя безопасно открыть:

```text
BLOCKED - EXISTING BRANCH/WORKTREE CONFLICT
```

Если найден реальный secret:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

Не начинать `003-02` в рамках этого prompt.

---

# 52. Явно отложенная работа

В report перечислить как deferred, а не как незавершённость `003-01`:

```text
003-02:
    IdentityService
    first-message onboarding
    MAX binding conflict detection
    safe MAX chat rotation
    eager notification settings creation
    onboarding concurrency retry

003-03:
    cryptography-based TokenCipher adapter
    versioned key ring
    key loading/config boundary
    encryption/decryption acceptance

003-04:
    KaitenConnectionService
    bind/replace
    disable
    get_active_connection_secret behavior
    stale credential snapshot compare-and-mark
    mark_needs_reauth behavior
    Kaiten credential verifier adapter integration
```

---

## Главное правило этапа

`003-01` не должен интерпретировать финальную спецификацию заново.

Он буквально переводит frozen contract:

```text
003-00a
```

в:

```text
typed frozen DTOs
+
application error hierarchy
+
Protocol ports
+
safe import surface
+
contract tests
```

Без service behavior, external integration, encryption implementation, repository changes или schema changes.
