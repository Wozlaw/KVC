# 002-03 — Minimal repository and query contracts implementation

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Текущая ветка:

```text
002 — MVP service data model
```

Предыдущие этапы успешно приняты:

```text
002-00   MVP service data model audit
002-00a  Final MVP service data model specification
002-00b  Kaiten deadline semantics correction
002-00c  Live Kaiten deadline acceptance probe
002-01   SQLAlchemy models + initial Alembic migration
002-01a  Python 3.12 clean gate
002-02   Live PostgreSQL persistence acceptance
```

Основной входной отчёт:

```text
codex/reports/002_02_live_postgresql_persistence_acceptance_report.md
```

`002-02` завершён:

```text
ACCEPTED LIVE POSTGRESQL PERSISTENCE - READY FOR 002-03
```

На этом этапе необходимо реализовать **минимальный async repository/query layer** поверх уже принятой семитабличной схемы.

Это не бизнес-сервис, не Kaiten/MAX integration и не command-processing layer.

---

# 1. Главная цель

Реализовать persistence primitives, необходимые следующим слоям KVC:

```text
user identity
MAX chat binding
Kaiten connection lookup/storage
active dialog session
active PendingCommand
notification settings
notification dedup/reservation history
```

Repository layer должен:

- использовать существующий `AsyncSession`;
- не владеть commit/rollback;
- поддерживать явные transaction boundaries;
- использовать row-level locking там, где это необходимо;
- физически enforce application-level ownership invariant;
- использовать PostgreSQL-native atomic operations для notification dedup;
- не добавлять бизнес-логику команд;
- не обращаться к Kaiten/MAX/GigaChat;
- не менять schema.

После `002-03` application layer должен иметь безопасные persistence primitives для будущих message handlers/workers.

---

# 2. Нормативные документы

Перед реализацией изучи:

```text
codex/reports/002_00a_mvp_service_data_model_final_specification.md
codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
codex/reports/002_01_mvp_service_data_model_implementation_report.md
codex/reports/002_01a_python312_persistence_clean_gate_report.md
codex/reports/002_02_live_postgresql_persistence_acceptance_report.md
```

Также изучи:

```text
src/kvc_persistence/base.py
src/kvc_persistence/models.py
src/kvc_persistence/engine.py
src/kvc_persistence/session.py
src/kvc_persistence/
tests/
pyproject.toml
```

Не проектируй persistence model заново.

Приоритет contract:

```text
002-00c
002-00b
002-00a
```

---

# 3. Frozen schema — запрещено менять

На `002-03` не менять:

```text
tables
columns
types
nullability
PK
FK
ON DELETE
CHECK
UNIQUE
partial UNIQUE
secondary indexes
server defaults
Alembic revision
```

Схема остаётся:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

Особенно сохранить:

```text
notification_history.due_at
notification_history.due_date_time_present
```

и отсутствие:

```text
notification_history.due_date
```

Не создавать новую migration, если repository implementation не выявила реальный schema defect.

---

# 4. Runtime

Использовать только project runtime:

```text
.venv\Scripts\python.exe
Python 3.12.x
```

Перед работой:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip check
```

Не использовать Python 3.14 fallback.

---

# 5. Repository architecture

Сначала изучи текущую package structure и выбери минимальное расположение repository layer.

Предпочтительно coherent package, например:

```text
src/kvc_persistence/repositories/
```

но не навязывай эту структуру, если существующие conventions проекта требуют иной.

Не создавать:

- generic framework;
- abstract repository hierarchy без необходимости;
- UnitOfWork abstraction, если project session layer уже предоставляет transaction boundary;
- service locator;
- dependency injection framework.

Repository classes/functions должны быть простыми и явно типизированными.

---

# 6. Transaction ownership contract

Ключевое правило:

> Repository methods **не вызывают `commit()` и не вызывают `rollback()`**.

Transaction lifecycle принадлежит caller/application layer.

Допустимо:

```text
execute
scalar/scalars
flush
refresh
```

если это требуется persistence operation.

Пример ожидаемой orchestration semantics:

```python
async with session.begin():
    ...
    await repository_method(...)
    ...
```

Не скрывать transaction boundary внутри каждого repository call.

Добавь tests/code review assertions, подтверждающие отсутствие внутренних commits.

---

# 7. Session contract

Repositories должны работать с:

```text
sqlalchemy.ext.asyncio.AsyncSession
```

Предпочтительно:

```python
class ...Repository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
```

или эквивалентный минимальный контракт.

Не создавать новый engine/session factory внутри repository.

---

# 8. `UserRepository`

Минимально реализовать primitives:

```text
get_by_id(user_id)
get_by_id_for_update(user_id)
create(...)
set_status(...)
```

Если `set_status()` добавляет лишнюю business semantics, допустимо оставить generic explicit update primitive, но API должен быть узким.

`create()`:

- принимает application-generated UUID либо создаёт ORM object с accepted UUID default;
- не commit;
- flush допустим.

Не добавлять поиск по email/name — таких полей нет.

---

# 9. `MaxChatRepository`

Минимальные query contracts:

```text
get_by_max_chat_id(max_chat_id)
get_private_by_max_user_id(max_user_id)
get_primary_for_user(user_id)
create_private_binding(...)
```

Repository не должен поддерживать group chat.

`chat_type` остаётся:

```text
PRIVATE
```

Создание binding не должно автоматически создавать user или notification settings скрытым side effect.

Такие composition transactions принадлежат будущему application layer.

Не использовать реальные MAX API данные в tests.

---

# 10. `KaitenConnectionRepository`

Минимально:

```text
get_for_user(user_id)
get_for_user_for_update(user_id)
create(...)
update_connection(...)
```

Repository принимает только:

```text
encrypted_api_token: bytes
```

и не выполняет encryption/decryption.

Запрещено:

```text
plaintext token column
logging token
repr token
test with real token
```

`update_connection()` не должен менять architectural cardinality `1 user -> 1 connection`.

---

# 11. `DialogSessionRepository`

Это concurrency-sensitive repository.

Минимально реализовать:

```text
get_active_for_user(user_id)
get_active_for_user_for_update(user_id)
get_or_create_active(...)
update_context(...)
end(...)
```

## 11.1. Concurrency rule при создании active dialog

Partial UNIQUE гарантирует:

```text
one active dialog per user
```

Но repository должен избегать обычной race:

```text
request A -> no active session
request B -> no active session
A insert
B insert -> IntegrityError
```

Предпочтительный transaction primitive:

1. lock parent `users` row через `SELECT ... FOR UPDATE`;
2. re-read active dialog;
3. если существует — вернуть его;
4. если нет — создать;
5. flush.

Это сериализует создание active dialog для одного user без distributed lock.

Если найден более простой и столь же доказуемый PostgreSQL/SQLAlchemy pattern — допускается использовать его, но обоснуй.

Не использовать advisory locks без необходимости.

---

# 12. Dialog context update contract

`update_context()` может обновлять только accepted context fields:

```text
max_chat_binding_id
current_board_id
current_board_name
current_card_id
current_card_title
previous_user_message
previous_bot_message
last_card_list
last_card_list_at
expires_at
```

Не превращать repository в transcript/history service.

Не сохранять Kaiten card/comments как отдельные rows.

---

# 13. `PendingCommandRepository`

Минимально реализовать:

```text
get_active_for_session(dialog_session_id)
get_active_for_session_for_update(dialog_session_id)
create_active(...)
update_resolution_state(...)
update_fields(...) — только если узкий typed API нецелесообразен
```

Не реализовывать full business state machine.

Transitions:

```text
RECEIVED -> ...
```

будут валидироваться application/business layer позже.

Но repository обязан обеспечить **ownership invariant**.

---

# 14. PendingCommand ownership invariant — обязательная реализация

Frozen invariant:

```text
pending_commands.user_id == dialog_sessions.user_id
where pending_commands.dialog_session_id = dialog_sessions.id
```

В `002-01` runtime enforcement был намеренно deferred до `002-03`.

Теперь он должен быть реализован.

## При `create_active(...)`

Обязательная последовательность:

1. получить `dialog_session` по `dialog_session_id`;
2. использовать `SELECT ... FOR UPDATE` на session row;
3. если session отсутствует — не создавать command;
4. сравнить:

```text
dialog_session.user_id
requested user_id
```

5. при mismatch — выбросить explicit persistence invariant exception;
6. проверить active pending command в той же transaction;
7. если active command уже существует — вернуть/сигнализировать согласно explicit repository contract;
8. если нет — insert + flush.

DB partial UNIQUE остаётся final concurrency guard.

Не добавлять composite FK или DB trigger.

---

# 15. Persistence invariant exception

Если в проекте нет подходящего exception type, добавь минимальный persistence exception, например:

```text
PersistenceInvariantError
```

или более точное имя.

Не строить большую exception hierarchy.

Exception message:

- не содержит secrets;
- содержит достаточный diagnostic context;
- не раскрывает encrypted token.

Tests должны проверять mismatch invariant.

---

# 16. Pending command state mutations

Repository layer не должен решать, разрешён ли переход:

```text
READY -> EXECUTED
NEEDS_CLARIFICATION -> RESOLVING
...
```

Но должен предоставлять persistence primitive для application layer.

Предпочтительно typed method, например:

```text
update_state(command, state, ...)
```

или небольшой набор узких методов.

Не создавай finite-state-machine engine в `002-03`.

---

# 17. Clarification locking primitive

Для будущего clarification handler должен существовать safe path:

```text
get active pending command FOR UPDATE
```

После lock caller сможет:

- re-check state;
- изменить candidates/unresolved_entity;
- increment clarification_attempts;
- update state.

Repository не должен commit.

Добавить query/test, подтверждающий `FOR UPDATE`.

---

# 18. `NotificationSettingsRepository`

Минимально:

```text
get_for_user(user_id)
get_for_user_for_update(user_id)
get_or_create_for_user(user_id)
list_enabled(...)
```

## Creation concurrency

Для `get_or_create_for_user()` можно использовать тот же parent lock pattern:

```text
lock users row
read settings
insert if absent
```

Не создавать hidden default settings при обычном read.

`list_enabled()` должен возвращать deterministic iterable/list для будущего worker.

Не реализовывать scheduler.

---

# 19. `NotificationHistoryRepository`

Это второй concurrency-sensitive repository.

Минимально:

```text
reserve(...)
get_by_dedup_key(...)
get_by_id_for_update(...)
mark_sent(...)
mark_failed(...)
```

Не реализовывать MAX send.

---

# 20. Atomic notification reservation

`reserve()` должен реализовать dedup атомарно на PostgreSQL.

Использовать PostgreSQL-native:

```text
INSERT ... ON CONFLICT DO NOTHING
```

по accepted unique key:

```text
user_id
kaiten_card_id
due_at
due_date_time_present
notification_type
```

Предпочтительно:

```text
RETURNING
```

чтобы различать:

```text
reservation created
duplicate already exists
```

Контракт может быть:

```text
NotificationHistory | None
```

или explicit result object, но не усложняй API без необходимости.

Не реализовывать:

```text
exactly-once
outbox
MAX idempotency
retry scheduler
```

---

# 21. Notification deadline semantics

Repository **не интерпретирует** deadline.

Он получает уже нормализованные:

```text
due_at
due_date_time_present
```

и сохраняет их буквально.

Live-verified rule из `002-00c` остаётся responsibility будущего Kaiten/application layer:

```text
date-only -> UTC date component of read-back due_at
date-time -> exact instant
```

Repository не timezone-convert `due_at`.

---

# 22. Notification delivery status persistence

Допустимые statuses определены DB:

```text
RESERVED
SENT
FAILED
```

Repository methods:

```text
mark_sent(...)
mark_failed(...)
```

должны только обновлять persistence fields:

```text
delivery_status
sent_at / failed_at
error_type
```

Не реализовывать retry policy.

`error_type` должен принимать safe code/classification, а не stack trace/secret.

---

# 23. FAILED/stale RESERVED recovery — не расширять scope

`002-00b/00c` зафиксировали future recovery semantics.

В `002-03` достаточно primitives:

```text
get_by_id_for_update
mark/reserve status updates
```

Не реализовывать:

- reclaim scheduler;
- attempt_count;
- retry backoff;
- stale reservation worker.

Не менять schema.

---

# 24. Query style

Использовать SQLAlchemy 2.x:

```text
select()
update()
PostgreSQL insert()
with_for_update()
```

Избегать legacy:

```text
session.query(...)
```

Все queries должны быть типизированы насколько разумно.

---

# 25. Explicit ordering

Любой repository method, возвращающий список, должен иметь deterministic ordering.

Не полагаться на implicit PostgreSQL row order.

Для `list_enabled()` выбрать устойчивый order, например:

```text
user_id
```

или accepted stable key.

---

# 26. No hidden lazy DB traffic

Если ORM relationships в моделях отсутствуют — не добавлять их только ради repositories.

Repository queries должны явно описывать нужные tables.

Не вводить N+1 через accidental lazy-loading.

---

# 27. Isolation and tenant/user ownership

Все user-scoped repository methods должны принимать/фильтровать `user_id`, где это требуется contract.

Не позволять method с user context случайно возвращать row другого user.

Особенно:

```text
dialog_sessions
pending_commands
kaiten_connections
notification_settings
notification_history
```

Добавить tests на ownership/isolation.

---

# 28. Live PostgreSQL integration tests

Repository semantics, особенно:

```text
FOR UPDATE
partial UNIQUE
ON CONFLICT
```

нельзя полноценно доказать SQLite.

Добавить отдельные PostgreSQL integration tests.

Использовать configured development DB:

```text
kvc_dev
```

только если:

```text
app_env = development
current Alembic revision = 00201_mvp_service_model
```

Если safety prerequisite не выполнен — integration tests должны explicit skip/fail согласно project test convention, но не мутировать неизвестную DB.

---

# 29. Integration test data safety

Использовать только synthetic:

```text
UUIDs
MAX IDs
Kaiten IDs
encrypted token bytes
```

Не использовать:

- live Kaiten token;
- real card ID;
- real MAX IDs.

Каждый integration test должен:

- использовать уникальные synthetic identifiers;
- cleanup/rollback;
- не оставлять rows.

После integration suite проверить row counts либо выполнить targeted cleanup.

---

# 30. Integration tests — minimum matrix

Реализовать минимум следующие cases.

## User

```text
create/get
get_for_update
status update persistence
```

## MAX

```text
get_by_max_chat_id
private lookup
primary lookup
create binding
```

## Kaiten connection

```text
create encrypted bytes
get_for_user
update
no plaintext field/path
```

## Dialog

```text
get_or_create active
same user returns same active session
end active -> create next
FOR UPDATE query path
```

## PendingCommand

```text
create active
active lookup
ownership match accepted
ownership mismatch rejected
active session row locked
second active command handled safely
terminal old command allows next active
```

## Notification settings

```text
get_or_create
defaults
list_enabled deterministic
```

## Notification history

```text
first reserve -> created
same dedup reserve -> duplicate/None
different due_at -> created
mark_sent
mark_failed
```

---

# 31. Concurrency-focused tests

Минимально доказать repository concurrency design.

Не обязательно строить stress-test на сотни tasks.

Нужно проверить:

1. generated SQL для lock path содержит `FOR UPDATE`;
2. parent-lock pattern используется при active dialog creation;
3. dialog-session lock используется при PendingCommand creation;
4. notification reservation использует PostgreSQL `ON CONFLICT DO NOTHING`;
5. DB partial unique остаётся final guard.

Если реализовать реальный two-session concurrency test над PostgreSQL безопасно и детерминированно — сделай его для одного критического case.

Не добавлять flaky sleep-based tests.

---

# 32. Transaction ownership test

Проверить, что repositories не commit самостоятельно.

Минимум:

1. создать row через repository;
2. `rollback()` caller session;
3. открыть новую session;
4. убедиться, что row отсутствует.

Это должно доказать caller-owned transaction contract.

---

# 33. Repository API return contract

Не возвращать raw SQLAlchemy `Row` наружу без необходимости.

Предпочтительно возвращать:

```text
ORM model
None
list[ORM model]
```

или минимальный explicit result type для reserve operation.

Не вводить DTO layer в `002-03`.

---

# 34. No business integrations

На этом этапе запрещено:

- HTTP calls to Kaiten;
- MAX API calls;
- GigaChat/STT calls;
- command parsing;
- entity resolver;
- summary generation;
- notification scheduling;
- bot handlers.

Repositories должны быть infrastructure-only.

---

# 35. No encryption implementation

`KaitenConnectionRepository` работает только с:

```text
encrypted_api_token: bytes
```

Криптографический service появится отдельно.

Не добавлять encryption key access в repository.

---

# 36. No schema migration

`002-03` не должен менять физическую schema.

Перед и после работы:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

Ожидается:

```text
00201_mvp_service_model
No new upgrade operations detected
```

Если repository code приводит к metadata drift — это ошибка.

---

# 37. Existing database final state

После integration tests database должна остаться:

```text
alembic_version = 00201_mvp_service_model
```

и synthetic repository test rows должны отсутствовать.

Не выполнять downgrade в `002-03`.

---

# 38. Tests organization

Следуй существующим test conventions.

Предпочтительно разделить:

```text
unit/structural repository tests
integration/PostgreSQL repository tests
```

если такая структура соответствует проекту.

Если pytest markers используются, зарегистрировать marker корректно.

Не создавать warning, который ломает:

```text
pytest -W error
```

---

# 39. Quality gate

После implementation выполнить:

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

Также отдельно показать результат targeted repository tests.

---

# 40. Git discipline

Не выполнять commit автоматически.

Перед началом:

```powershell
git status --short
git log --oneline --decorate -5
git diff --check
```

Не изменять:

```text
.env
.venv
.python312
```

Не удалять prompts/reports предыдущих этапов.

---

# 41. Что допускается исправлять

Если repository implementation выявляет очевидный code-level defect в ORM model API, который **не меняет frozen physical schema**, допускается минимальная correction.

Если требуется schema change:

```text
STOP
```

и определить, является ли это:

- implementation defect предыдущего этапа;
- архитектурным изменением.

Без отдельного решения не создавать новую migration.

---

# 42. Итоговый report

Создай:

```text
codex/reports/002_03_repository_query_contracts_implementation_report.md
```

Report должен содержать минимум:

1. Executive summary.
2. Baseline repository/database state.
3. Repository package architecture.
4. Transaction ownership contract.
5. Session contract.
6. `UserRepository` API.
7. `MaxChatRepository` API.
8. `KaitenConnectionRepository` API.
9. `DialogSessionRepository` API.
10. Active-dialog locking strategy.
11. `PendingCommandRepository` API.
12. Ownership invariant implementation.
13. Pending-command locking strategy.
14. Persistence invariant exception contract.
15. `NotificationSettingsRepository` API.
16. `NotificationHistoryRepository` API.
17. Atomic reservation implementation.
18. Deadline persistence semantics.
19. Explicit out-of-scope business logic.
20. Unit/structural tests.
21. PostgreSQL integration tests.
22. Transaction rollback/no-hidden-commit proof.
23. Ownership/isolation tests.
24. Concurrency/locking tests.
25. Notification dedup tests.
26. Database cleanup verification.
27. Alembic current/check result.
28. Full quality gate.
29. Changed files.
30. Deferred application/business work.
31. Final status.

---

# 43. Changed-files classification

В report:

```text
Production code:
Repositories:
Tests:
Alembic:
Configuration:
Documentation:
Reports:
Database state:
Other:
```

Ожидается:

```text
Alembic:
none
```

если schema не менялась.

Database final state:

```text
00201_mvp_service_model
synthetic repository test rows = 0
```

---

# 44. Acceptance criteria

`002-03` считается успешно завершённым только если:

- repository layer реализован поверх существующего AsyncSession;
- repository methods не commit/rollback самостоятельно;
- user/MAX/Kaiten binding queries реализованы;
- active dialog queries реализованы;
- active-dialog creation сериализуется безопасным lock pattern;
- PendingCommand queries реализованы;
- `pending_commands.user_id == dialog_sessions.user_id` реально enforce repository layer;
- PendingCommand creation использует row lock;
- clarification-safe `FOR UPDATE` primitive существует;
- notification settings queries реализованы;
- notification reserve использует atomic PostgreSQL `ON CONFLICT DO NOTHING`;
- notification repository не интерпретирует deadline/timezone;
- no plaintext Kaiten token path создан;
- no business integrations добавлены;
- no schema migration добавлена;
- PostgreSQL integration tests проходят;
- synthetic rows после tests отсутствуют;
- caller-owned rollback доказан;
- `alembic current = 00201_mvp_service_model`;
- `alembic check` не показывает drift;
- pytest проходит;
- `pytest -W error` проходит;
- Ruff проходит;
- mypy проходит;
- report создан.

---

# 45. Final status

Если всё успешно:

```text
IMPLEMENTED - READY FOR 002 BRANCH ACCEPTANCE/CLOSEOUT
```

Если repository implementation требует schema change или нового architecture decision:

```text
BLOCKED - PERSISTENCE ARCHITECTURE DECISION REQUIRED
```

Если configured PostgreSQL не является безопасной development DB для integration tests:

```text
BLOCKED - SAFE DEVELOPMENT DATABASE REQUIRED
```

---

## Главное правило

`002-03` должен добавить **минимальные, безопасные и транзакционно явные persistence primitives**.

Он не должен превращаться в:

```text
application service layer
Kaiten adapter
MAX bot
command state machine
notification worker
generic repository framework
```

После этого этапа ветка `002` должна иметь полный foundation:

```text
schema
+
ORM
+
migration
+
live PostgreSQL acceptance
+
repository/query contracts
```

и быть готовой к отдельной branch acceptance/closeout.
