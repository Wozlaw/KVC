# 002-00a — Final MVP service data model specification

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Текущая ветка разработки: **002 — MVP service data model**.

Предыдущий этап `002-00` завершён аудитом модели данных:

```text
codex/reports/002_00_mvp_service_data_model_audit_report.md
```

Аудит принят пользователем. На этом этапе необходимо **зафиксировать окончательную спецификацию сервисной модели данных MVP** с учётом принятых решений и точечных архитектурных уточнений.

Это **спецификационный этап**.

Не реализовывай SQLAlchemy-модели, Alembic migration, repositories, query layer или бизнес-логику.
К реализации `002-01` переходить только после отдельного подтверждения пользователя.

---

## Главная цель

Подготовить окончательную, непротиворечивую и пригодную для непосредственной реализации спецификацию первой бизнес-модели PostgreSQL для KVC.

Результат должен однозначно определить:

- какие данные принадлежат KVC;
- какие данные остаются исключительно в Kaiten;
- состав таблиц;
- поля и PostgreSQL-типы;
- PK/FK;
- UNIQUE и partial UNIQUE;
- CHECK constraints;
- индексы;
- `ON DELETE`;
- жизненный цикл `PendingCommand`;
- диалоговый контекст;
- хранение Kaiten token;
- уведомления и deduplication;
- временные данные и retention;
- timestamp/timezone contract;
- transaction/concurrency invariants;
- точный состав будущей первой Alembic migration.

После этого документа у `002-01` не должно оставаться архитектурных вопросов по структуре БД.

---

# 1. Обязательная исходная база

В первую очередь изучи:

```text
codex/reports/002_00_mvp_service_data_model_audit_report.md
```

Также проверь:

- действующую спецификацию MVP проекта;
- архитектурные документы репозитория;
- результаты ветки `001`;
- текущую конфигурацию SQLAlchemy/Alembic;
- принятую naming convention constraints/indexes;
- существующие conventions проекта.

Не заменяй решения аудита собственным новым проектированием, если только не обнаружено объективное внутреннее противоречие.

Если найдено противоречие, зафиксируй его в отчёте, но не начинай самостоятельное расширение scope.

---

# 2. Зафиксированные архитектурные границы

Следующие положения считаются принятыми и **не подлежат пересмотру на этом этапе**.

## 2.1. Kaiten — единственный source of truth

KVC **не хранит постоянную локальную копию**:

- spaces;
- boards;
- columns;
- cards;
- comments;
- due dates как карточечные сущности;
- attachments;
- card position/state;
- иные объекты Kaiten.

Допускаются только:

- внешние Kaiten ID;
- краткоживущие display snapshots;
- resolver candidates;
- диалоговый контекст;
- notification dedup markers.

Нельзя превращать JSONB-поля в скрытый локальный cache Kaiten.

---

## 2.2. KVC хранит только собственное сервисное состояние

Первая модель должна включать семь таблиц:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

Не добавляй новые бизнес-таблицы без доказанной необходимости.

---

# 3. Решения пользователя, обязательные для финальной спецификации

Все семь решений из `002-00` считаются утверждёнными.

## Decision 1 — Internal PK

Использовать:

```text
UUID
```

UUID генерируется приложением.

Не использовать `BIGINT IDENTITY`.

Не вводить PostgreSQL extension только ради UUID generation.

---

## Decision 2 — MAX scope

MVP поддерживает только:

```text
PRIVATE 1:1 chat
```

Group chats в модель MVP не включать.

Если потребуется guard/check для chat type — зафиксировать только `PRIVATE`.

---

## Decision 3 — Kaiten connections

В MVP:

```text
1 KVC user -> 1 Kaiten connection
```

Не проектировать multi-workspace / multi-account selection UX.

Связь должна быть защищена соответствующим UNIQUE constraint.

---

## Decision 4 — PendingCommand terminal states

Помимо states исходной спецификации обязательно включить:

```text
FAILED
CANCELLED
EXPIRED
```

Итоговый набор:

```text
RECEIVED
PARSED
RESOLVING
NEEDS_CLARIFICATION
READY
EXECUTED
FAILED
CANCELLED
EXPIRED
```

Активными считаются:

```text
RECEIVED
PARSED
RESOLVING
NEEDS_CLARIFICATION
READY
```

Терминальными:

```text
EXECUTED
FAILED
CANCELLED
EXPIRED
```

---

## Decision 5 — Notification delivery state

В `notification_history` использовать:

```text
RESERVED
SENT
FAILED
```

Схема должна обеспечивать безопасную минимальную reservation/dedup semantics без полноценного outbox.

---

## Decision 6 — Timezone

`notification_settings.timezone` хранить с default:

```text
UTC
```

Использовать IANA timezone string.

Не зашивать региональный timezone продукта или сервера.

---

## Decision 7 — User deletion

Физическое удаление пользователя в MVP **не реализуется**.

Использовать:

```text
users.status = ACTIVE | DISABLED
```

Не добавлять `deleted_at`.

Не проектировать cascade physical account deletion.

---

# 4. Обязательные уточнения после аудита

Кроме семи решений выше, финальная спецификация должна устранить следующие нюансы.

---

## 4.1. Семантика ссылки `dialog_sessions -> max_chats`

В `002-00` поле:

```text
dialog_sessions.max_chat_id
```

предложено как:

```text
UUID FK -> max_chats.id
```

при этом в самой таблице `max_chats`:

```text
max_chats.max_chat_id
```

является внешним MAX identifier типа `TEXT`.

Такое именование семантически неоднозначно.

### Требование

В финальной спецификации внутреннюю FK-ссылку назвать:

```text
max_chat_binding_id
```

Тип:

```text
UUID
```

FK:

```text
dialog_sessions.max_chat_binding_id
    -> max_chats.id
    ON DELETE SET NULL
```

Название `max_chat_id` зарезервировано для внешнего идентификатора MAX в таблице `max_chats`.

Не допускать двух разных смыслов одного имени поля.

---

## 4.2. Не создавать дублирующие индексы поверх UNIQUE

Проверить весь candidate schema.

Если UNIQUE constraint / partial UNIQUE уже создаёт пригодный PostgreSQL index для соответствующего query pattern, **не создавать второй идентичный secondary index**.

В частности проверить:

```text
max_chats.max_chat_id
max_chats.max_user_id
max_chats.user_id WHERE is_primary
kaiten_connections.user_id
dialog_sessions.user_id WHERE ended_at IS NULL
pending_commands.dialog_session_id WHERE state IN (...)
notification_history dedup tuple
```

### Правило

В финальной спецификации должно быть явно записано:

> Secondary index не создаётся поверх идентичного UNIQUE/partial UNIQUE index без отдельного доказанного query pattern.

Нужно представить итоговый список индексов **без логического дублирования**.

---

## 4.3. Ownership invariant для `pending_commands`

Сохраняем одновременно:

```text
pending_commands.user_id
pending_commands.dialog_session_id
```

Это осознанная денормализация для:

- прямых user-scoped queries;
- tenant/user isolation;
- recovery/debug;
- удобства repository layer.

Но необходимо формально закрепить инвариант:

```text
pending_commands.user_id
==
dialog_sessions.user_id
для строки dialog_sessions.id = pending_commands.dialog_session_id
```

### Требование

Не усложнять первую схему составным FK только ради данного инварианта, если это не требуется существующей моделью.

Инвариант должен обеспечиваться:

- application/repository layer;
- транзакционной логикой создания `PendingCommand`;
- обязательными тестами на этапе реализации.

Финальная спецификация должна явно обозначить это как **cross-row ownership invariant**.

---

# 5. Таблицы, которые необходимо специфицировать окончательно

Для каждой таблицы дай одну окончательную таблицу полей с колонками:

```text
Field
PostgreSQL type
NULL
Default
Constraint
Meaning
Data class
```

Data class использовать как минимум из категорий:

```text
internal identity
external reference
persistent configuration
secret
transient dialog context
transient workflow state
audit/dedup state
lifecycle metadata
```

---

## 5.1. `users`

Назначение:

- внутренняя identity KVC user;
- service status.

Базовый контракт из аудита сохранить:

```text
id UUID PK
status TEXT NOT NULL DEFAULT ACTIVE
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

Допустимые `status`:

```text
ACTIVE
DISABLED
```

Физическое удаление в MVP не проектировать.

---

## 5.2. `max_chats`

Назначение:

- bind MAX identity/chat к KVC user;
- deterministic incoming routing;
- primary destination для replies/notifications.

External MAX IDs пока хранить как `TEXT`.

MVP chat type:

```text
PRIVATE
```

Нужно окончательно определить:

- PK;
- FK;
- UNIQUE / partial UNIQUE;
- CHECK;
- индексы;
- `ON DELETE`.

Не создавать лишний индекс на `max_chat_id`, если UNIQUE уже покрывает lookup.

---

## 5.3. `kaiten_connections`

Назначение:

- пользовательская Kaiten connection;
- encrypted API token;
- verification status.

Сохраняем одну connection на user.

External Kaiten IDs — `TEXT`, пока контракт API не требует иного.

Kaiten token:

```text
encrypted at rest
```

В этом этапе определить только storage contract.

Не реализовывать encryption code.

Обязательно сохранить:

```text
token_encryption_version
```

и запрет хранения encryption key в PostgreSQL.

---

## 5.4. `dialog_sessions`

Назначение:

- bounded persisted conversational context;
- restart-safe dialog state;
- не является transcript storage.

Один active dialog session на user.

Обязательно использовать:

```text
max_chat_binding_id UUID NULL
```

а не внутренний FK под именем `max_chat_id`.

Сохранить:

```text
current_board_id
current_board_name
current_card_id
current_card_title
previous_user_message
previous_bot_message
last_card_list
last_card_list_at
expires_at
ended_at
created_at
updated_at
```

`last_card_list` остаётся bounded JSONB response snapshot.

Не вводить отдельную таблицу card list items.

Не создавать JSONB GIN index.

---

## 5.5. `pending_commands`

Назначение:

- durable transient state для команды;
- entity resolution;
- clarification;
- safe continuation после restart.

Один active pending command на active dialog session.

Сохранить JSONB:

```text
arguments
unresolved_entity
candidates
```

JSONB является transient interpreter/resolver state, а не durable domain model.

Обязательно зафиксировать полный state machine и partial UNIQUE для активных состояний.

Также отдельно описать ownership invariant:

```text
pending_commands.user_id == owner of dialog_session_id
```

---

## 5.6. `notification_settings`

Назначение:

- `/notify on`;
- `/notify off`;
- `/notify status`;
- due-soon threshold;
- user timezone.

Default:

```text
enabled = false
due_soon_days = 1
timezone = UTC
```

Диапазон `due_soon_days` сохранить ограниченным.

Если аудит предлагает `0..30` и нет причин менять — зафиксировать его.

---

## 5.7. `notification_history`

Назначение:

- notification deduplication;
- concurrency reservation;
- минимальный delivery audit.

Dedup key:

```text
user_id
kaiten_card_id
due_date
notification_type
```

`due_date` обязателен в dedup key.

Notification types:

```text
DUE_SOON
DUE_TODAY
OVERDUE
```

Delivery states:

```text
RESERVED
SENT
FAILED
```

Не вводить полноценный outbox в этой ветке.

---

# 6. PendingCommand state machine

Отдельным разделом спецификации зафиксировать state machine.

Основной путь:

```text
RECEIVED
  ->
PARSED
  ->
RESOLVING
  ->
READY
  ->
EXECUTED
```

Clarification loop:

```text
RESOLVING
  ->
NEEDS_CLARIFICATION
  ->
RESOLVING
```

Допустимые terminal exits:

```text
FAILED
CANCELLED
EXPIRED
```

Нужно определить:

- active states;
- terminal states;
- допустимые переходы;
- условия переходов;
- что происходит при повторном clarification reply;
- `clarification_attempts`;
- TTL semantics;
- `executed_at`;
- handling external Kaiten failure.

Не нужно реализовывать state machine в коде на этом этапе.

---

# 7. JSONB contracts

Сохрани подход аудита и формализуй versioned JSON contracts как минимум для:

```text
dialog_sessions.last_card_list
pending_commands.arguments
pending_commands.unresolved_entity
pending_commands.candidates
```

Каждый контракт должен иметь:

```json
{
  "version": 1
}
```

или эквивалентную versioned структуру.

Нужно ясно указать:

- что является обязательным;
- что optional;
- какие external IDs хранятся;
- что snapshots являются временными;
- что JSONB не является локальной моделью Kaiten.

Не добавляй GIN indexes без query requirement.

---

# 8. Secret storage contract

Отдельно зафиксировать.

## Не хранятся в PostgreSQL

```text
PostgreSQL password
MAX bot token
MAX webhook secret, если используется
GigaChat credentials
SaluteSpeech credentials
token encryption key
.env contents
```

## Хранится в PostgreSQL

Только пользовательский Kaiten API token:

```text
encrypted_api_token
```

Требования:

- plaintext token никогда не persisted;
- plaintext token не логируется;
- plaintext token не попадает в repr;
- plaintext token не попадает в migrations;
- plaintext token не попадает в reports;
- real token не используется в test fixtures;
- encryption key приходит из environment/external secret storage;
- `token_encryption_version` поддерживает будущую ротацию.

Не реализовывать криптографию в `002-00a`.

---

# 9. Timestamp / timezone contract

Зафиксировать:

```text
TIMESTAMPTZ
```

для всех instants:

```text
created_at
updated_at
last_verified_at
last_card_list_at
expires_at
ended_at
executed_at
sent_at
failed_at
```

Все instants:

```text
UTC
timezone-aware
```

Для календарного Kaiten deadline использовать:

```text
DATE
```

если Kaiten API действительно представляет deadline как calendar date без времени.

Notification classification вычисляется относительно:

```text
notification_settings.timezone
```

а не timezone сервера.

---

# 10. Constraints policy

Для небольших конечных наборов значений сохранить стратегию:

```text
TEXT + CHECK
```

Не использовать PostgreSQL ENUM в первой миграции.

Причины должны быть зафиксированы:

- проще Alembic evolution;
- DB-level constraint сохраняется;
- application enum может зеркалить CHECK;
- не нужны lookup tables для малых статических state sets.

Проверить naming convention проекта и привести все constraint names к ней.

---

# 11. Индексы

Подготовить окончательную query/index matrix.

Для каждого индекса указать:

```text
query scenario
table
lookup/filter
index/constraint
unique?
partial?
reason
```

Особенно проверить:

### Incoming MAX route

```text
max_chats.max_chat_id
```

### MAX private identity binding

```text
max_user_id + PRIVATE
```

### Primary chat by user

```text
user_id WHERE is_primary
```

### Kaiten connection by user

```text
kaiten_connections.user_id
```

### Active dialog

```text
user_id WHERE ended_at IS NULL
```

### Active pending command

```text
dialog_session_id
WHERE state IN active states
```

### Pending recovery/debug

```text
(user_id, state)
```

### Expiration scan

Только если такой индекс действительно нужен первой реализации.

### Notification scan

```text
enabled = true
```

### Notification dedup

```text
(user_id, kaiten_card_id, due_date, notification_type)
```

Исключить дублирование UNIQUE и обычных secondary indexes.

---

# 12. Transaction boundaries

Финальная спецификация должна явно задать минимальные atomic operations.

Как минимум:

## MAX binding

В одной транзакции:

```text
create/find user
create/update MAX binding
create default notification_settings if required
```

## Kaiten binding

```text
encrypt token outside DB
insert/update kaiten_connections
update status/verification metadata
```

## Dialog update

```text
find/create active dialog
lock active session
update dialog context
```

## Pending command creation

```text
insert pending command
update dialog context
```

в одной транзакции.

## Clarification handling

```text
lock active pending command
verify current state
update resolver state/candidates
update dialog context
```

## Command completion

После результата внешней операции Kaiten:

```text
update pending command state
timestamps
context
```

## Notification send

Логика:

```text
attempt RESERVED insert
if conflict -> duplicate -> skip
send MAX
update SENT or FAILED
```

Не проектировать distributed locking.

---

# 13. Concurrency invariants

Явно зафиксировать следующие invariants:

```text
one active dialog session per user
one active pending command per dialog session
one notification reservation per dedup key
clarification reply cannot mutate terminal command
duplicate webhook message must not create conflicting active state
```

Определить, какие invariants защищаются:

- DB constraints;
- partial UNIQUE indexes;
- row-level locking;
- application/repository checks;
- transaction boundaries.

Отдельно указать ownership invariant `pending_commands.user_id`.

---

# 14. ON DELETE contract

Для каждой FK дать окончательное `ON DELETE`.

Исходный подход аудита считать предпочтительным:

```text
users -> children                 RESTRICT
max_chats -> dialog_sessions      SET NULL
dialog_sessions -> pending_commands CASCADE
```

Но теперь FK в `dialog_sessions` должен называться:

```text
max_chat_binding_id
```

Не проектировать физическое удаление пользователя.

---

# 15. Retention / cleanup

Не добавляй отдельную subsystem реализации cleanup.

Но спецификация должна разделить:

## Persistent

```text
users
max_chats
kaiten_connections
notification_settings
notification_history
```

## Transient / TTL-managed

```text
dialog_sessions
pending_commands
previous messages
last_card_list
resolver candidates
```

Нужно определить, какие rows могут позднее удаляться cleanup job после TTL/terminal state.

Не вводить soft delete без принятого требования.

---

# 16. Первая Alembic migration — только спецификация

Не создавай migration.

Но финальный документ должен дать точный future migration contract:

## Tables

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

## Upgrade order

Указать точный порядок создания с учётом FK.

## Downgrade order

Указать обратный безопасный порядок удаления.

## Included

- PK;
- FK;
- UNIQUE;
- partial UNIQUE;
- CHECK;
- необходимые indexes;
- defaults;
- server/application default policy;
- PostgreSQL types.

## Excluded

Не включать:

- seed data без отдельного требования;
- Kaiten content;
- token encryption implementation;
- repositories;
- services;
- worker;
- MAX integration;
- Kaiten API integration;
- GigaChat/SaluteSpeech integration;
- cleanup implementation;
- outbox.

---

# 17. Проверка согласованности схемы

Перед финальным выводом обязательно проверить:

1. Каждый FK указывает на существующий PK/UNIQUE target.
2. Нет циклической зависимости, мешающей первой migration.
3. Нет двух полей с одинаковым именем и разной семантикой.
4. Нет дублирующих indexes.
5. Все partial UNIQUE predicates согласованы с state definitions.
6. Все default values входят в CHECK constraints.
7. `NULL` semantics не ломают UNIQUE rules.
8. One-active-session invariant физически enforceable PostgreSQL.
9. One-active-command invariant физически enforceable PostgreSQL.
10. Notification dedup key физически enforceable PostgreSQL.
11. `pending_commands.user_id` ownership invariant явно задокументирован.
12. JSONB не используется как замена реляционной модели стабильных данных.
13. Kaiten entities не превращены в локальный persistent cache.
14. Secret storage contract не допускает plaintext persistence.
15. Timezone/date semantics непротиворечивы.

---

# 18. Что нельзя делать

Запрещено на этапе `002-00a`:

- менять production Python code;
- создавать SQLAlchemy ORM models;
- создавать Alembic revision;
- выполнять `alembic upgrade`;
- создавать таблицы вручную;
- менять `.env`;
- менять secret handling implementation;
- добавлять repositories;
- добавлять Kaiten client;
- добавлять MAX bot;
- добавлять notification worker;
- реализовывать encryption;
- начинать `002-01`;
- расширять schema будущими non-MVP сущностями;
- добавлять local Kaiten cache.

---

# 19. Обязательный итоговый документ

Создай:

```text
codex/reports/002_00a_mvp_service_data_model_final_specification.md
```

Документ должен быть **самодостаточной реализационной спецификацией**, а не кратким дополнением к `002-00`.

Он должен содержать минимум:

1. Executive summary.
2. Accepted architectural decisions.
3. Data ownership boundary.
4. Final table inventory.
5. Final field specification по каждой таблице.
6. PK/FK/UNIQUE/CHECK.
7. Final ON DELETE matrix.
8. Final index/query matrix.
9. PendingCommand state machine.
10. Dialog context contract.
11. JSONB contracts.
12. Secret storage contract.
13. Timestamp/timezone contract.
14. Notification dedup/delivery contract.
15. Transaction boundaries.
16. Concurrency invariants.
17. Ownership invariant для `pending_commands`.
18. Retention/cleanup classification.
19. Exact first migration specification.
20. Upgrade/downgrade order.
21. Explicit out-of-scope list.
22. Consistency review.
23. Changed files.
24. Quality gate.
25. Final status.

---

# 20. Проверки репозитория

Так как production code изменяться не должен, выполни baseline quality gate, принятый проектом.

Как минимум:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src
git diff --check
git status --short
```

Если какая-либо команда отличается в текущем репозитории, используй актуальный проектный эквивалент и объясни это в отчёте.

Не исправляй несвязанные проблемы автоматически.

---

# 21. Git discipline

Не коммить изменения автоматически.

В отчёте покажи:

```text
git status --short
git diff --check
git diff --stat
```

Отдельно перечисли:

```text
Production code changes:
Tests:
Documentation:
Report:
Other:
```

Ожидаемый результат этого этапа:

```text
Production code changes:
none

Tests:
none
```

Допустимы только необходимые спецификационные/отчётные файлы.

---

# 22. Критерий завершения

Этап считается успешно завершённым только если:

- все решения `002-00` окончательно зафиксированы;
- неоднозначность `dialog_sessions.max_chat_id` устранена через `max_chat_binding_id`;
- список индексов очищен от дублирования;
- ownership invariant `pending_commands.user_id` формализован;
- все семь таблиц полностью специфицированы;
- state machine `PendingCommand` непротиворечива;
- notification reservation/dedup contract однозначен;
- secret boundary однозначен;
- timezone/date semantics однозначны;
- первая migration описана настолько точно, что `002-01` не требует нового архитектурного решения;
- production code не изменён;
- quality gate пройден либо объективно описаны baseline failures.

---

# 23. Ожидаемый финальный статус

Если архитектурных блокеров больше нет:

```text
ACCEPTED SPECIFICATION — READY FOR 002-01
```

Если обнаружено реальное противоречие, которое нельзя разрешить из уже принятых решений:

```text
BLOCKED — USER DECISION REQUIRED
```

В таком случае не начинай реализацию и перечисли **только действительно необходимые** решения пользователя.

---

## Главное правило этапа

`002-00a` должен завершить проектирование первой сервисной БД KVC.

После него структура данных должна считаться **замороженным MVP-контрактом для реализации `002-01`**, если пользователь отдельно не изменит требования.
