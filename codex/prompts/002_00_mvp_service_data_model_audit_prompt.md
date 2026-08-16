# 002-00 — Audit of MVP service data model and opening branch 002

## Проект

**Kaiten Voice Control**

Новая проектная ветка:

```text
002 — MVP service data model
```

Текущий этап:

```text
002-00 — Audit of MVP service data model
```

Это **аудит и проектирование**, а не реализация.

---

# 1. Контекст предыдущей ветки

Ветка `001` завершила инфраструктурный фундамент проекта.

Принятые этапы:

```text
001-01   Project bootstrap
001-01a  TestClient dependency cleanup
001-02   Configuration, PostgreSQL persistence and Alembic foundation
001-02a  Live PostgreSQL acceptance
```

Текущий подтверждённый инфраструктурный baseline:

```text
Python 3.12
FastAPI / ASGI
Hypercorn
Pydantic / pydantic-settings
PostgreSQL 18.6
SQLAlchemy 2.x async
asyncpg
Alembic
pytest
ruff
mypy
```

Локальная PostgreSQL-конфигурация:

```text
host:     127.0.0.1
port:     5432
database: kvc_dev
role:     kvc_user
```

Подтверждён реальный application path:

```text
.env
  ↓
AppSettings
  ↓
KVC_DATABASE_URL
  ↓
SQLAlchemy AsyncEngine
  ↓
asyncpg
  ↓
PostgreSQL
  ↓
SELECT 1
  ↓
AsyncSession
  ↓
health probe
  ↓
Alembic online diagnostics
```

Текущая БД не содержит предметных таблиц Kaiten Voice Control.

Служебная таблица:

```text
public.alembic_version
```

существует как результат online-диагностики Alembic и не является предметной таблицей.

Alembic revisions пока отсутствуют.

---

# 2. Основные источники истины для аудита

Перед началом обязательно изучить:

```text
docs/specifications/Kaiten Voice Control — спецификация MVP v0.1.md
AGENTS.md
README.md
docs/architecture/
docs/operations/
src/kvc_config/
src/kvc_persistence/
src/kvc_domain/
src/kvc_application/
src/kvc_notifications/
src/kvc_worker/
tests/
alembic.ini
src/kvc_persistence/migrations/
```

Также изучить отчёты ветки `001`:

```text
codex/reports/001_01_project_bootstrap_environment_codex_git_report.md
codex/reports/001_01a_testclient_dependency_cleanup_report.md
codex/reports/001_02_configuration_postgresql_persistence_alembic_foundation_report.md
codex/reports/001_02a_live_postgresql_acceptance_report.md
```

Если в репозитории присутствуют более свежие спецификации или архитектурные решения, сопоставить их с MVP-спецификацией и явно указать расхождения.

Не заменять требования спецификации предположениями.

---

# 3. Цель аудита

Спроектировать первую предметную PostgreSQL-схему сервиса Kaiten Voice Control, достаточную для MVP, **до начала реализации**.

Аудит должен ответить:

1. какие собственные данные сервис действительно обязан хранить;
2. какие данные остаются исключительно в Kaiten;
3. какие таблицы нужны в MVP;
4. какие поля, типы, ключи и ограничения нужны каждой таблице;
5. как должны быть связаны пользователи, MAX, Kaiten и диалоговые сессии;
6. как хранить контекст диалога;
7. как хранить `PendingCommand`;
8. как реализовать notification settings/history и защиту от дублей;
9. какие данные являются секретами и в каком виде они должны храниться;
10. какие индексы необходимы;
11. какие FK/cascade/restrict правила необходимы;
12. какие timestamps нужны;
13. какие состояния/enum/check constraints нужны;
14. какие решения требуют отдельного подтверждения пользователя;
15. какой должна быть первая содержательная Alembic migration.

---

# 4. Главный предметный инвариант

Согласно MVP:

> Kaiten является единственным источником истины для содержимого проекта.

Собственная БД сервиса **не должна постоянно копировать**:

- spaces;
- boards;
- columns;
- cards;
- card descriptions;
- comments;
- due dates;
- attachments;
- card position/state.

Допускается хранить только идентификаторы/ссылки на объекты Kaiten, которые необходимы для:

- контекста пользователя;
- разрешения текущей карточки/доски;
- `PendingCommand`;
- уведомлений;
- технической корреляции.

Аудит должен особенно проверить, чтобы проектируемая схема не превращалась в теневую копию Kaiten.

---

# 5. Минимальный набор сущностей из MVP-спецификации

Спецификация предлагает:

```text
users
kaiten_connections
max_chats
dialog_sessions
pending_commands
notification_settings
notification_history
```

Это **исходный**, но не автоматически окончательный набор.

Для каждой сущности определить:

- нужна ли она действительно;
- её ответственность;
- обязательные поля;
- nullable-поля;
- PK;
- external IDs;
- FK;
- uniqueness;
- indexes;
- timestamps;
- lifecycle;
- delete policy;
- security concerns.

Если нужна дополнительная техническая сущность — обосновать её.

Если какая-либо предлагаемая таблица лишняя или может быть безопасно объединена с другой — показать альтернативу и аргументы.

---

# 6. `users`

Провести аудит пользовательской модели.

Нужно определить минимум:

- внутренний ID пользователя;
- дата создания;
- дата изменения;
- активность/статус пользователя, если действительно нужна;
- связь с MAX identity;
- связь с Kaiten connection;
- связь с настройками уведомлений;
- связь с активной диалоговой сессией/сессиями.

Ключевой вопрос:

> Что является устойчивой внутренней идентичностью пользователя сервиса, а что — внешним идентификатором MAX/Kaiten?

Не использовать username/display name как PK.

Оценить предпочтительный PK:

```text
UUID
BIGINT identity
```

и обосновать выбор для данного сервиса.

---

# 7. `max_chats`

Определить модель связи пользователя с MAX.

Нужно выяснить по спецификации и будущей интеграции, какие внешние идентификаторы реально понадобятся:

- MAX user ID;
- MAX chat ID;
- тип чата, если нужен;
- текущий/основной чат;
- created_at/updated_at;
- уникальные ограничения.

Нужно отдельно оценить:

- может ли один пользователь иметь несколько MAX chats;
- может ли один chat соответствовать нескольким пользователям;
- нужно ли поддерживать group chat в MVP;
- или MVP следует жёстко ограничить private user chat.

Если API MAX ещё не интегрирован и точные типы external IDs неизвестны, не придумывать числовой диапазон. Предложить безопасный тип хранения и явно пометить вопрос как требующий проверки документации MAX перед реализацией.

---

# 8. `kaiten_connections`

Определить минимальную модель подключения Kaiten.

Нужно рассмотреть:

- внутренний ID connection;
- user_id;
- Kaiten account/workspace/space identifier, если нужен;
- API endpoint/base URL, если он может различаться;
- encrypted API token;
- created_at;
- updated_at;
- last_verified_at, если обоснован;
- enabled/disabled state, если нужен.

Главное требование:

> Kaiten API token хранится только в зашифрованном виде.

Аудит должен определить **контракт хранения**, но не реализовывать криптографию.

Нужно зафиксировать:

- plaintext token не хранится;
- encryption key не хранится в PostgreSQL;
- encryption key должен поступать из environment/secret storage;
- логи и repr не раскрывают token;
- миграции не содержат token/key.

Оценить, нужен ли отдельный:

```text
token_encryption_version
```

или аналогичный version marker для будущей ротации ключей.

Не усложнять без необходимости, но отметить последствия выбранного решения.

---

# 9. `dialog_sessions`

Спецификация требует контекст как минимум:

```text
current_board
current_card
previous_user_message
previous_bot_message
last_card_list
pending_command
```

Провести отдельный аудит структуры хранения.

Необходимо определить:

- одна активная сессия на пользователя или история сессий;
- связь с MAX chat;
- current_board как Kaiten external ID и/или display name;
- current_card как Kaiten external ID и/или display name;
- previous_user_message;
- previous_bot_message;
- last_card_list;
- timestamps;
- expiration/cleanup policy.

Особенно оценить:

```text
last_card_list
```

поскольку он нужен для ответов вида:

```text
вторую
```

после выдачи списка карточек.

Определить, что лучше для MVP:

- JSONB snapshot списка кандидатов;
- отдельная таблица элементов списка;
- иной минимальный вариант.

При выборе учитывать, что список является **временным контекстом**, а не постоянной копией Kaiten.

---

# 10. `pending_commands`

Это одна из ключевых сущностей MVP.

Спецификация задаёт lifecycle:

```text
RECEIVED
 ↓
PARSED
 ↓
RESOLVING
 ↓
NEEDS_CLARIFICATION
 ↓
READY
 ↓
EXECUTED
```

с возможными переходами:

```text
RESOLVING
↕
NEEDS_CLARIFICATION
```

Аудит должен определить:

- PK;
- user/session relation;
- intent;
- original_message;
- parsed arguments;
- unresolved entity;
- candidate list;
- state;
- created_at;
- updated_at;
- executed_at;
- failure/cancel state, если без него lifecycle неполон;
- retry/expiration policy;
- возможность иметь более одного незавершённого PendingCommand.

Особенно проработать вопрос:

> Должен ли у одной dialog session быть максимум один active pending command?

Если да — определить, как это обеспечить:

- application invariant;
- partial unique index;
- иной PostgreSQL constraint.

Разобрать хранение:

```text
arguments
unresolved_entity
candidates
```

и сравнить варианты:

```text
JSONB
нормализованные таблицы
гибрид
```

Для MVP предпочтение должно быть минимальной, но проверяемой структуре.

Не нормализовывать transient AI payload без реальной пользы.

---

# 11. Состояния `PendingCommand`

Проверить, достаточно ли состояний спецификации.

Не менять их молча.

Если необходимы технические terminal states, например:

```text
FAILED
CANCELLED
EXPIRED
```

нужно:

1. обосновать необходимость;
2. показать сценарий;
3. отделить обязательное для MVP от возможного расширения.

Также оценить способ хранения state:

- PostgreSQL ENUM;
- TEXT + CHECK;
- application enum + CHECK;
- иной вариант.

Аргументировать выбор с точки зрения Alembic migrations и будущего расширения.

---

# 12. `notification_settings`

Спецификация требует:

```text
/notify on
/notify off
/notify status
```

и настраиваемый порог предварительного уведомления.

Исходная политика:

```text
за 1 день
в день срока
после наступления просрочки
```

Аудит должен определить минимальные поля:

- user_id;
- enabled;
- due_soon threshold;
- timezone, если требуется;
- created_at/updated_at.

Ключевой вопрос:

> Где должна жить пользовательская timezone и нужна ли она уже в MVP?

Учитывать, что сроки Kaiten могут быть календарной датой без времени, а сервер production будет работать независимо от локальной timezone пользователя.

Не делать timezone неявно зависимой от timezone сервера.

---

# 13. `notification_history`

Спецификация требует защиту от повторных уведомлений.

Минимальный логический ключ:

```text
user_id
card_id
due_date
notification_type
sent_at
```

Типы:

```text
DUE_SOON
DUE_TODAY
OVERDUE
```

Нужно спроектировать deduplication contract.

Обязательно рассмотреть unique constraint, который не позволит отправить одно и то же событие повторно при каждом polling cycle.

Нужно учесть:

> При изменении срока карточки старое уведомление не должно блокировать уведомления по новому сроку.

Поэтому в deduplication key должен участвовать due date / due marker.

Аудит должен определить:

- точный уникальный ключ;
- тип due value;
- timezone/date semantics;
- внешний `card_id`;
- notification type representation;
- sent_at;
- возможную ошибку доставки и нужно ли её хранить.

Не проектировать полноценную message queue/outbox, если она не требуется MVP.

Но отдельно отметить риск:

```text
DB recorded as sent
↔
MAX message actually delivered
```

и предложить минимальную стратегию на будущее, не обязательно включённую в первую migration.

---

# 14. Идентификаторы внешних систем

Для Kaiten и MAX определить общую политику external IDs.

Не предполагать без проверки, что внешний ID всегда помещается в PostgreSQL INTEGER.

Сравнить:

```text
TEXT
BIGINT
UUID
```

и выбрать тип только после проверки фактического API-контракта либо использовать безопасный универсальный тип до интеграционного аудита.

Нужно исключить ситуацию, когда первая migration жёстко фиксирует неверный тип внешнего ID.

---

# 15. Временные данные против постоянных данных

Каждое поле классифицировать:

```text
persistent identity/configuration
persistent audit/dedup state
transient dialog context
external reference
secret
```

Для transient context определить:

- нужен ли TTL;
- когда очищается;
- что происходит при новой команде;
- что происходит после EXECUTED;
- что происходит при рестарте сервера.

Основной принцип:

> Контекст должен переживать restart сервера, но не превращаться в бесконечный журнал переписки.

---

# 16. Timestamps

Зафиксировать единый timestamp contract.

Оценить использование:

```text
TIMESTAMP WITH TIME ZONE
```

и хранение времени в UTC.

Не использовать naive datetime без явного обоснования.

Для каждой таблицы определить, нужны ли:

```text
created_at
updated_at
executed_at
sent_at
last_verified_at
expires_at
```

Не добавлять timestamps «на всякий случай».

---

# 17. Delete / cascade policy

Для каждого FK определить:

```text
CASCADE
RESTRICT
SET NULL
NO ACTION
```

Особенно рассмотреть:

- удаление пользователя;
- удаление Kaiten connection;
- удаление MAX chat binding;
- удаление dialog session;
- удаление pending command;
- notification history.

Не использовать `ON DELETE CASCADE` повсеместно без анализа.

Отдельно определить:

> Нужен ли физический delete пользователя в MVP или достаточно disabled/deactivated state?

Если этот вопрос выходит за текущую спецификацию — вынести на подтверждение пользователя.

---

# 18. Soft delete

Не вводить soft delete автоматически.

Для каждой сущности оценить, действительно ли нужен:

```text
deleted_at
is_deleted
```

Если нет реального use case — не добавлять.

---

# 19. Индексы

Предложить только обоснованные индексы.

Обязательно проанализировать будущие query patterns:

```text
MAX incoming message
  → lookup by max user/chat id

user
  → active dialog session

dialog session
  → current pending command

notification worker
  → enabled users/settings

notification dedup
  → user/card/due/type

Kaiten connection
  → by user
```

Для каждого предлагаемого индекса указать, какой запрос он обслуживает.

Не индексировать все FK/JSONB автоматически без объяснения.

---

# 20. JSONB policy

Отдельно определить, где JSONB уместен.

Вероятные кандидаты:

```text
last_card_list
pending command arguments
unresolved_entity
candidates
```

Для каждого JSONB поля:

- описать JSON schema / логический контракт;
- определить, нужно ли искать/фильтровать по вложенным полям;
- определить, нужен ли GIN index;
- указать, является ли payload versioned.

Не использовать JSONB для данных, которые являются устойчивыми нормализованными сущностями.

---

# 21. Constraints

Предложить ограничения PostgreSQL:

- NOT NULL;
- UNIQUE;
- CHECK;
- FK;
- partial unique indexes;
- length/domain checks, только если обоснованы.

Текущий SQLAlchemy naming convention использует:

```text
ck_%(table_name)s_%(constraint_name)s
```

Следовательно, будущим CHECK constraints следует давать явные семантические имена.

Аудит должен учитывать это при проектировании.

---

# 22. Сервисные состояния и enum policy

Составить инвентаризацию всех предполагаемых конечных наборов значений:

```text
PendingCommand state
Notification type
connection status, если нужен
user status, если нужен
```

Для каждого решить:

```text
DB enum
TEXT + CHECK
boolean
отдельная таблица-справочник
```

Не создавать справочники там, где достаточно простого CHECK/enum.

Не использовать boolean, если реальное состояние имеет более двух значений.

---

# 23. Конкурентность

MVP изначально multi-user.

Нужно оценить минимальные concurrency-инварианты:

- два webhook request от одного пользователя;
- одновременно incoming message и notification worker;
- два polling cycle;
- повторная обработка одного уточняющего ответа;
- duplicate notification attempt.

Не проектировать сложную distributed lock infrastructure.

Но определить, какие проблемы должны решаться:

- транзакцией;
- unique constraint;
- row lock;
- optimistic application check.

---

# 24. Транзакционные границы

Для будущих операций определить, какие изменения собственной БД должны быть атомарными.

Примеры:

```text
PendingCommand state transition
dialog context update
notification dedup record
binding user ↔ MAX
binding user ↔ Kaiten
```

Не проектировать Unit of Work abstraction в аудите, но определить необходимые transaction boundaries.

---

# 25. Безопасность и секреты

Проверить будущий data contract на отсутствие:

- plaintext Kaiten tokens;
- GigaChat credentials;
- MAX bot token;
- encryption key;
- `.env` contents;
- passwords.

Указать, какие секреты вообще **не должны храниться в service DB**.

Ожидаемый принцип:

```text
global application secrets
→ environment / secret storage

user Kaiten token
→ encrypted value in DB
```

Обосновать.

---

# 26. PostgreSQL/Alembic baseline audit

Выполнить только read-only/безопасную проверку текущей БД.

Минимально:

```powershell
python -m alembic -c alembic.ini heads
python -m alembic -c alembic.ini history
python -m alembic -c alembic.ini current
```

Проверить через PostgreSQL catalog текущие пользовательские таблицы.

Ожидаемо:

```text
public.alembic_version
```

и отсутствие предметных таблиц.

Не удалять `alembic_version`.

Не создавать migration.

Не выполнять DDL.

---

# 27. Git baseline

Проверить:

```powershell
git status --short
git log --oneline --decorate -5
git diff --check
```

Аудит должен явно показать:

- на каком commit начинается ветка 002;
- какие незакоммиченные изменения относятся ещё к ветке 001;
- чист ли baseline перед началом реализации 002.

Если изменения `001-02/001-02a` ещё не закоммичены, **не смешивать их молча с будущей реализацией 002**.

В таком случае в отчёте отметить:

```text
Branch 002 implementation should start only after accepted branch-001 changes are committed.
```

Не выполнять commit самостоятельно.

---

# 28. Что НЕ делать в 002-00

Запрещено:

- создавать SQLAlchemy business models;
- создавать Alembic revision;
- выполнять `CREATE TABLE`;
- изменять БД;
- создавать seed data;
- реализовывать repository;
- реализовывать services;
- реализовывать MAX/Kaiten/GigaChat/STT adapters;
- реализовывать encryption;
- реализовывать worker polling;
- реализовывать webhook;
- добавлять API endpoints;
- добавлять CLI;
- рефакторить инфраструктуру 001 без выявленного дефекта;
- ставить новые зависимости;
- выполнять commit/push.

Это **чистый аудит**.

---

# 29. Ожидаемый результат проектирования

В отчёте должна быть предложена **кандидатная схема MVP**.

Для каждой таблицы дать Markdown-таблицу:

| Поле | PostgreSQL type | NULL | Default | Constraint | Назначение |
|---|---|---|---|---|---|

Кроме полей показать:

```text
PK
FK
UNIQUE
CHECK
indexes
delete policy
```

---

# 30. Relationship matrix

Отдельно дать матрицу связей:

| Parent | Child | Cardinality | FK | ON DELETE | Обоснование |
|---|---|---|---|---|---|

---

# 31. Query/index matrix

Отдельно:

| Сценарий | Таблица | Условие поиска | Предлагаемый индекс | Обоснование |
|---|---|---|---|---|

---

# 32. Data ownership matrix

Обязательно:

| Данные | Источник истины | Хранится в KVC DB | Формат хранения | Причина |
|---|---|---:|---|---|

Включить минимум:

```text
Kaiten board
Kaiten card
Kaiten comments
Kaiten due date
Kaiten attachments
current_board
current_card
MAX identity
Kaiten token
dialog context
PendingCommand
notification settings
notification history
```

Это должно наглядно доказать, что KVC DB не дублирует Kaiten.

---

# 33. State machines

Если предлагаются состояния, показать таблицы переходов.

Минимум для `PendingCommand`:

| From | To | Условие | Terminal |
|---|---|---|---|

Отдельно перечислить переходы, прямо зафиксированные спецификацией, и дополнительные предлагаемые переходы.

Дополнительные состояния нельзя выдавать за уже принятые требования.

---

# 34. Вопросы для подтверждения пользователя

Отчёт должен закончиться отдельным разделом:

```text
Decisions requiring user approval
```

Включать только реальные архитектурные развилки.

Не спрашивать о мелочах, которые однозначно следуют из спецификации или нормальной инженерной практики.

Для каждого вопроса дать:

```text
Option A
Option B
Recommendation
Consequence
```

---

# 35. Предложение первой migration

Без её создания описать, что должна содержать первая реальная Alembic revision.

Например:

```text
revision purpose
tables
constraints
indexes
enums/checks
upgrade order
downgrade order
```

Не назначать окончательный revision ID заранее.

---

# 36. Предлагаемая последовательность ветки 002

По итогам аудита предложить дальнейшее разбиение ветки.

Предпочтительный принцип:

```text
002-00  audit
002-00a final data model specification after user decisions
002-01  first implementation/migration
002-02  persistence acceptance
...
```

Но конкретные этапы должны вытекать из результатов аудита.

Не раздувать ветку искусственно.

---

# 37. Quality gate самого аудита

Так как production-код не должен меняться, после аудита выполнить текущий baseline gate:

```powershell
python -m pip check
pytest
pytest -W error
ruff format --check .
ruff check .
mypy src
git diff --check
```

Ожидается отсутствие regression.

Если quality gate падает до изменений аудита, это отдельная находка и должна быть зафиксирована.

---

# 38. Отчёт

Создать:

```text
codex/reports/002_00_mvp_service_data_model_audit_report.md
```

Отчёт должен содержать:

## 38.1. Executive summary

Кратко:

- готов ли baseline к ветке 002;
- какие сущности действительно нужны;
- есть ли блокирующие вопросы.

## 38.2. Source requirements

Перечислить требования MVP, влияющие на собственную БД.

## 38.3. Current persistence baseline

- Git;
- PostgreSQL;
- Alembic;
- текущие таблицы;
- revisions.

## 38.4. Data ownership

Матрица источник истины / KVC storage.

## 38.5. Candidate schema

Полная кандидатная схема всех MVP-таблиц.

## 38.6. Relationships

FK/cardinality/delete policies.

## 38.7. PendingCommand design

Отдельный подробный раздел.

## 38.8. Dialog context design

Отдельный подробный раздел.

## 38.9. Notification data design

Settings, history, deduplication.

## 38.10. Secret storage contract

Особенно Kaiten token.

## 38.11. Timestamp/timezone contract

Единые правила.

## 38.12. Index/query matrix

Обоснование индексов.

## 38.13. Constraints and enum policy

CHECK/enum/unique/partial indexes.

## 38.14. Concurrency and transactions

Минимальные необходимые гарантии.

## 38.15. First migration proposal

Без реализации.

## 38.16. Decisions requiring user approval

Только реальные развилки.

## 38.17. Recommended branch plan

Следующие шаги ветки 002.

## 38.18. Quality gate

Фактические результаты baseline-тестов.

## 38.19. Final status

Один из:

```text
READY FOR SPECIFICATION
READY WITH DECISIONS REQUIRED
BLOCKED
FAIL
```

### READY FOR SPECIFICATION

Если все архитектурные решения однозначны и можно сразу подготовить `002-00a`.

### READY WITH DECISIONS REQUIRED

Если реализация возможна только после нескольких конкретных решений пользователя.

### BLOCKED

Если baseline ветки 001 не зафиксирован, схема БД неожиданно изменена или есть другое блокирующее состояние.

### FAIL

Если audit/quality gate выявил фундаментальный дефект инфраструктуры.

---

# 39. Критерий завершения 002-00

Этап завершён, если после отчёта можно однозначно ответить:

```text
WHAT service data KVC owns
WHERE it is stored
HOW tables relate
WHICH state is persistent
WHICH data is transient
HOW secrets are protected
HOW notifications are deduplicated
HOW dialog context survives restart
WHAT first migration must contain
WHICH decisions still need user approval
```

Никакая реализация схемы не выполняется до рассмотрения пользователем отчёта `002-00`.

После пользовательского подтверждения или снятия архитектурных вопросов следующим шагом должен стать отдельный final specification / implementation prompt.
